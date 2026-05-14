"""
AgriGuard - markets.py
FastAPI router for real-time agricultural market price intelligence.
Provides price comparisons, market rankings, trend analysis, and best-market recommendations.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/markets", tags=["Markets"])

# ── Data Path ─────────────────────────────────────────────────────────────────
DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "raw", "wfp_food_prices_uga.csv"
)


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class MarketPrice(BaseModel):
    market: str
    region: Optional[str]
    latest_price: float
    currency: str
    unit: str
    date_recorded: str
    price_30d_ago: Optional[float]
    price_change_pct: Optional[float]
    trend: str                      # "rising" | "falling" | "stable"
    data_points: int                # how many records back this market has


class CommodityMarketSummary(BaseModel):
    commodity: str
    markets: list[MarketPrice]
    best_market_to_sell: str        # highest price
    worst_market_to_sell: str       # lowest price
    price_spread: float             # max - min across markets
    national_avg_price: float
    currency: str
    unit: str
    recommendation: str
    generated_at: str


class MarketOverview(BaseModel):
    market: str
    region: Optional[str]
    total_commodities_tracked: int
    commodities: list[dict]         # [{commodity, latest_price, trend}]
    generated_at: str


class PriceHistoryPoint(BaseModel):
    date: str
    price: float
    market: str


class PriceHistoryResponse(BaseModel):
    commodity: str
    market: str
    currency: str
    unit: str
    history: list[PriceHistoryPoint]
    min_price: float
    max_price: float
    avg_price: float
    volatility_pct: float           # coefficient of variation


class TopMoverItem(BaseModel):
    commodity: str
    market: str
    latest_price: float
    previous_price: float
    change_pct: float
    direction: str                  # "up" | "down"
    currency: str


class TopMoversResponse(BaseModel):
    gainers: list[TopMoverItem]     # biggest price increases
    losers: list[TopMoverItem]      # biggest price drops
    period_days: int
    generated_at: str


# ── Data Loader ───────────────────────────────────────────────────────────────

def load_price_data() -> pd.DataFrame:
    """Load and normalise the WFP Uganda price CSV."""
    try:
        df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Price dataset not found. Ensure wfp_food_prices_uga.csv is in data/raw/."
        )

    df.columns = [c.strip().lower() for c in df.columns]

    rename_map = {}
    for col in df.columns:
        if "date" in col:
            rename_map[col] = "date"
        elif col in ("cmname", "commodity", "cm_name"):
            rename_map[col] = "commodity"
        elif col in ("mktname", "market", "mkt_name"):
            rename_map[col] = "market"
        elif col in ("price",):
            rename_map[col] = "price"
        elif col in ("cur", "currency", "currname"):
            rename_map[col] = "currency"
        elif col in ("unit", "um_name", "umname"):
            rename_map[col] = "unit"
        elif col in ("adm1name", "region", "admin1"):
            rename_map[col] = "region"
    df.rename(columns=rename_map, inplace=True)

    required = {"date", "commodity", "market", "price"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Dataset missing expected columns: {missing}"
        )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date", "price"], inplace=True)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df.dropna(subset=["price"], inplace=True)
    df["commodity"] = df["commodity"].str.strip().str.title()
    df["market"] = df["market"].str.strip().str.title()

    if "region" not in df.columns:
        df["region"] = None

    return df


# ── Helpers ───────────────────────────────────────────────────────────────────

def compute_trend(prices: pd.Series) -> str:
    """Determine trend direction from a price series."""
    if len(prices) < 2:
        return "stable"
    slope = np.polyfit(range(len(prices)), prices.values, 1)[0]
    pct = slope / (prices.mean() + 1e-9)
    if pct > 0.01:
        return "rising"
    elif pct < -0.01:
        return "falling"
    return "stable"


def latest_price_for(df: pd.DataFrame, commodity: str, market: str) -> Optional[dict]:
    """Return latest price record for a commodity-market pair."""
    subset = df[
        (df["commodity"].str.lower() == commodity.lower()) &
        (df["market"].str.lower() == market.lower())
    ].sort_values("date")

    if subset.empty:
        return None

    latest = subset.iloc[-1]
    currency = latest.get("currency", "UGX") if "currency" in subset.columns else "UGX"
    unit = latest.get("unit", "KG") if "unit" in subset.columns else "KG"

    # Price 30 days ago
    cutoff_30d = latest["date"] - timedelta(days=30)
    past = subset[subset["date"] <= cutoff_30d]
    price_30d = float(past.iloc[-1]["price"]) if not past.empty else None
    change_pct = None
    if price_30d:
        change_pct = round(((float(latest["price"]) - price_30d) / (price_30d + 1e-9)) * 100, 2)

    recent_prices = subset.tail(12)["price"]
    trend = compute_trend(recent_prices)

    return {
        "market": market,
        "region": latest.get("region") if "region" in subset.columns else None,
        "latest_price": round(float(latest["price"]), 2),
        "currency": currency,
        "unit": unit,
        "date_recorded": latest["date"].strftime("%Y-%m-%d"),
        "price_30d_ago": round(price_30d, 2) if price_30d else None,
        "price_change_pct": change_pct,
        "trend": trend,
        "data_points": len(subset),
    }


def build_sell_recommendation(
    commodity: str,
    best_market: str,
    worst_market: str,
    spread: float,
    avg: float,
    currency: str,
) -> str:
    """Return a plain-language farmer advisory."""
    spread_pct = round((spread / (avg + 1e-9)) * 100, 1)
    return (
        f"Sell {commodity} in {best_market} for the best price today. "
        f"Avoid {worst_market} — the price gap is {currency} {spread:,.0f} "
        f"({spread_pct}% difference). "
        f"Always compare prices before transporting your harvest."
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/summary/{commodity}", response_model=CommodityMarketSummary)
def commodity_market_summary(
    commodity: str,
    markets: Optional[str] = Query(
        default=None,
        description="Comma-separated markets to compare. Defaults to all available."
    ),
):
    """
    Compare current prices for one commodity across all (or selected) markets.
    Returns best/worst market to sell, national average, and a plain-language recommendation.

    Example: `/markets/summary/Maize?markets=Kampala,Mbarara,Gulu,Kabale`
    """
    df = load_price_data()
    commodity_title = commodity.strip().title()

    available = df[df["commodity"].str.lower() == commodity_title.lower()]["market"].unique()
    if len(available) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for '{commodity_title}'."
        )

    if markets:
        requested = [m.strip().title() for m in markets.split(",") if m.strip()]
        market_list = [m for m in requested if m in available]
        if not market_list:
            raise HTTPException(
                status_code=404,
                detail=f"None of the requested markets have data for '{commodity_title}'."
            )
    else:
        market_list = list(available)

    # Build MarketPrice objects
    market_prices: list[MarketPrice] = []
    for mkt in market_list:
        record = latest_price_for(df, commodity_title, mkt)
        if record:
            market_prices.append(MarketPrice(**record))

    if not market_prices:
        raise HTTPException(status_code=404, detail="Could not retrieve price data.")

    prices = [m.latest_price for m in market_prices]
    currency = market_prices[0].currency
    unit = market_prices[0].unit
    national_avg = round(float(np.mean(prices)), 2)
    spread = round(max(prices) - min(prices), 2)

    best = max(market_prices, key=lambda m: m.latest_price)
    worst = min(market_prices, key=lambda m: m.latest_price)

    recommendation = build_sell_recommendation(
        commodity_title, best.market, worst.market, spread, national_avg, currency
    )

    return CommodityMarketSummary(
        commodity=commodity_title,
        markets=sorted(market_prices, key=lambda m: m.latest_price, reverse=True),
        best_market_to_sell=best.market,
        worst_market_to_sell=worst.market,
        price_spread=spread,
        national_avg_price=national_avg,
        currency=currency,
        unit=unit,
        recommendation=recommendation,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/overview/{market}", response_model=MarketOverview)
def market_overview(market: str):
    """
    Get a full price overview of all commodities currently tracked in a specific market.

    Example: `/markets/overview/Kampala`
    """
    df = load_price_data()
    market_title = market.strip().title()

    subset = df[df["market"].str.lower() == market_title.lower()]
    if subset.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for market '{market_title}'."
        )

    region = subset["region"].iloc[-1] if "region" in subset.columns else None
    commodities_in_market = subset["commodity"].unique()

    commodity_summaries = []
    for comm in sorted(commodities_in_market):
        record = latest_price_for(df, comm, market_title)
        if record:
            commodity_summaries.append({
                "commodity": comm,
                "latest_price": record["latest_price"],
                "currency": record["currency"],
                "unit": record["unit"],
                "trend": record["trend"],
                "date_recorded": record["date_recorded"],
            })

    return MarketOverview(
        market=market_title,
        region=region,
        total_commodities_tracked=len(commodity_summaries),
        commodities=commodity_summaries,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/history/{commodity}", response_model=PriceHistoryResponse)
def price_history(
    commodity: str,
    market: str = Query(default="Kampala"),
    days: int = Query(default=180, ge=30, le=1825, description="History window in days (30–1825)"),
):
    """
    Fetch historical price series for a commodity in a market.
    Used to power charts on the farmer dashboard.

    Example: `/markets/history/Beans?market=Mbarara&days=365`
    """
    df = load_price_data()
    commodity_title = commodity.strip().title()
    market_title = market.strip().title()

    cutoff = df["date"].max() - timedelta(days=days)
    subset = df[
        (df["commodity"].str.lower() == commodity_title.lower()) &
        (df["market"].str.lower() == market_title.lower()) &
        (df["date"] >= cutoff)
    ].sort_values("date")

    if subset.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data for '{commodity_title}' in '{market_title}'."
        )

    currency = subset["currency"].iloc[-1] if "currency" in subset.columns else "UGX"
    unit = subset["unit"].iloc[-1] if "unit" in subset.columns else "KG"
    prices = subset["price"].values
    volatility = round(float(np.std(prices) / (np.mean(prices) + 1e-9)) * 100, 2)

    history = [
        PriceHistoryPoint(
            date=row["date"].strftime("%Y-%m-%d"),
            price=round(float(row["price"]), 2),
            market=market_title,
        )
        for _, row in subset.iterrows()
    ]

    return PriceHistoryResponse(
        commodity=commodity_title,
        market=market_title,
        currency=currency,
        unit=unit,
        history=history,
        min_price=round(float(prices.min()), 2),
        max_price=round(float(prices.max()), 2),
        avg_price=round(float(prices.mean()), 2),
        volatility_pct=volatility,
    )


@router.get("/movers", response_model=TopMoversResponse)
def top_movers(
    period_days: int = Query(default=30, ge=7, le=90, description="Lookback period in days"),
    top_n: int = Query(default=5, ge=1, le=20, description="Number of top movers to return"),
):
    """
    Returns the biggest price gainers and losers across ALL commodities and markets
    over the past N days.

    Useful for the AgriGuard dashboard alert feed.

    Example: `/markets/movers?period_days=14&top_n=5`
    """
    df = load_price_data()
    latest_date = df["date"].max()
    cutoff = latest_date - timedelta(days=period_days)

    movers = []
    for (commodity, market), group in df.groupby(["commodity", "market"]):
        group = group.sort_values("date")
        recent = group[group["date"] >= cutoff]
        past = group[group["date"] < cutoff]

        if recent.empty or past.empty:
            continue

        latest_p = float(recent.iloc[-1]["price"])
        prev_p = float(past.iloc[-1]["price"])
        change_pct = ((latest_p - prev_p) / (prev_p + 1e-9)) * 100
        currency = recent.iloc[-1].get("currency", "UGX") if "currency" in recent.columns else "UGX"

        movers.append({
            "commodity": commodity,
            "market": market,
            "latest_price": round(latest_p, 2),
            "previous_price": round(prev_p, 2),
            "change_pct": round(change_pct, 2),
            "direction": "up" if change_pct >= 0 else "down",
            "currency": currency,
        })

    movers_df = pd.DataFrame(movers)
    if movers_df.empty:
        raise HTTPException(status_code=404, detail="Not enough data to compute movers.")

    gainers = (
        movers_df[movers_df["direction"] == "up"]
        .sort_values("change_pct", ascending=False)
        .head(top_n)
        .to_dict(orient="records")
    )
    losers = (
        movers_df[movers_df["direction"] == "down"]
        .sort_values("change_pct", ascending=True)
        .head(top_n)
        .to_dict(orient="records")
    )

    return TopMoversResponse(
        gainers=[TopMoverItem(**g) for g in gainers],
        losers=[TopMoverItem(**l) for l in losers],
        period_days=period_days,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/compare/{commodity}", response_model=list[MarketPrice])
def compare_prices(
    commodity: str,
    markets: str = Query(
        default="Kampala,Mbarara,Gulu,Kabale,Jinja",
        description="Comma-separated list of markets to compare"
    ),
):
    """
    Side-by-side latest price comparison for a commodity across markets.
    Returns results sorted highest price first — so the farmer immediately
    sees the best place to sell.

    Example: `/markets/compare/Maize?markets=Kampala,Mbarara,Gulu,Kabale`
    """
    df = load_price_data()
    commodity_title = commodity.strip().title()
    market_list = [m.strip().title() for m in markets.split(",") if m.strip()]

    results = []
    for mkt in market_list:
        record = latest_price_for(df, commodity_title, mkt)
        if record:
            results.append(MarketPrice(**record))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No price data found for '{commodity_title}' in the requested markets."
        )

    return sorted(results, key=lambda m: m.latest_price, reverse=True)
