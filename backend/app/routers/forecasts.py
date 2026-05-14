"""
AgriGuard - forecasts.py
FastAPI router for agricultural price forecasting.
Uses Prophet + XGBoost to predict future crop prices.
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

router = APIRouter(prefix="/forecasts", tags=["Forecasts"])

# ── Path to your WFP CSV ──────────────────────────────────────────────────────
DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "raw", "wfp_food_prices_uga.csv"
)


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class ForecastPoint(BaseModel):
    date: str
    predicted_price: float
    lower_bound: float
    upper_bound: float
    confidence: float


class ForecastResponse(BaseModel):
    commodity: str
    market: str
    currency: str
    unit: str
    horizon_days: int
    forecast: list[ForecastPoint]
    trend: str          # "rising" | "falling" | "stable"
    alert: Optional[str]
    generated_at: str


class CommodityListResponse(BaseModel):
    commodities: list[str]
    markets: list[str]


# ── Helper: load & clean data ─────────────────────────────────────────────────

def load_price_data() -> pd.DataFrame:
    """Load WFP Uganda price CSV and return a cleaned DataFrame."""
    try:
        df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Price dataset not found. Ensure wfp_food_prices_uga.csv is in data/raw/."
        )

    # Normalise column names to lowercase
    df.columns = [c.strip().lower() for c in df.columns]

    # Common WFP column name variants → standardise
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
    return df


def get_trend_label(prices: list[float]) -> str:
    """Simple linear trend over last N points."""
    if len(prices) < 2:
        return "stable"
    slope = np.polyfit(range(len(prices)), prices, 1)[0]
    pct = slope / (np.mean(prices) + 1e-9)
    if pct > 0.01:
        return "rising"
    elif pct < -0.01:
        return "falling"
    return "stable"


def build_alert(trend: str, commodity: str, pct_change: float) -> Optional[str]:
    """Return a human-readable alert if price movement is significant."""
    if abs(pct_change) < 5:
        return None
    direction = "rise" if trend == "rising" else "fall"
    return (
        f"⚠️ {commodity} prices expected to {direction} by "
        f"~{abs(pct_change):.1f}% over the forecast period."
    )


# ── Prophet forecast (primary) ────────────────────────────────────────────────

def prophet_forecast(series: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """
    Run Facebook Prophet on a (date, price) series.
    Returns a DataFrame with columns: ds, yhat, yhat_lower, yhat_upper.
    Falls back to simple linear extrapolation if Prophet is unavailable.
    """
    try:
        from prophet import Prophet  # type: ignore
        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.15,
            seasonality_prior_scale=10,
        )
        train = series.rename(columns={"date": "ds", "price": "y"})
        m.fit(train)
        future = m.make_future_dataframe(periods=horizon, freq="D")
        forecast = m.predict(future)
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(horizon).reset_index(drop=True)

    except ImportError:
        logger.warning("Prophet not installed — falling back to linear extrapolation.")
        return linear_extrapolation(series, horizon)


def linear_extrapolation(series: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Fallback: simple linear regression extrapolation."""
    prices = series["price"].values
    x = np.arange(len(prices))
    slope, intercept = np.polyfit(x, prices, 1)
    std = np.std(prices) * 0.1  # 10 % uncertainty band

    last_date = series["date"].max()
    rows = []
    for i in range(1, horizon + 1):
        yhat = intercept + slope * (len(prices) + i)
        rows.append({
            "ds": last_date + timedelta(days=i),
            "yhat": max(yhat, 0),
            "yhat_lower": max(yhat - std, 0),
            "yhat_upper": yhat + std,
        })
    return pd.DataFrame(rows)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/commodities", response_model=CommodityListResponse)
def list_commodities():
    """Return all available commodities and markets in the dataset."""
    df = load_price_data()
    return CommodityListResponse(
        commodities=sorted(df["commodity"].unique().tolist()),
        markets=sorted(df["market"].unique().tolist()),
    )


@router.get("/{commodity}", response_model=ForecastResponse)
def get_forecast(
    commodity: str,
    market: str = Query(default="Kampala", description="Market name, e.g. Kampala"),
    horizon: int = Query(default=14, ge=1, le=90, description="Forecast horizon in days (1–90)"),
):
    """
    Forecast crop prices for a given commodity and market.

    - **commodity**: e.g. `Maize`, `Beans`, `Tomatoes`
    - **market**: e.g. `Kampala`, `Mbarara`, `Gulu`
    - **horizon**: number of days ahead to forecast (default 14)
    """
    df = load_price_data()

    # Filter
    commodity_title = commodity.strip().title()
    market_title = market.strip().title()

    subset = df[
        (df["commodity"].str.lower() == commodity_title.lower()) &
        (df["market"].str.lower() == market_title.lower())
    ].sort_values("date")

    if subset.empty:
        # Try commodity-only (any market)
        subset = df[df["commodity"].str.lower() == commodity_title.lower()].sort_values("date")
        if subset.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for commodity '{commodity_title}'. "
                       f"Use /forecasts/commodities to see available options."
            )
        market_title = subset["market"].mode()[0]  # most common market

    # Keep last 2 years for training (or all if less)
    cutoff = subset["date"].max() - timedelta(days=730)
    train = subset[subset["date"] >= cutoff][["date", "price"]].copy()

    if len(train) < 5:
        raise HTTPException(
            status_code=422,
            detail=f"Not enough data points ({len(train)}) to forecast '{commodity_title}' in '{market_title}'."
        )

    # Currency / unit metadata
    currency = subset["currency"].iloc[-1] if "currency" in subset.columns else "UGX"
    unit = subset["unit"].iloc[-1] if "unit" in subset.columns else "KG"

    # Run forecast
    fc = prophet_forecast(train, horizon)

    # Build response points
    points = []
    for _, row in fc.iterrows():
        points.append(ForecastPoint(
            date=row["ds"].strftime("%Y-%m-%d"),
            predicted_price=round(float(row["yhat"]), 2),
            lower_bound=round(float(row["yhat_lower"]), 2),
            upper_bound=round(float(row["yhat_upper"]), 2),
            confidence=round(
                1 - (row["yhat_upper"] - row["yhat_lower"]) / (abs(row["yhat"]) + 1e-9), 3
            ),
        ))

    # Trend & alert
    predicted_prices = [p.predicted_price for p in points]
    trend = get_trend_label(predicted_prices)
    first_price = train["price"].iloc[-1]
    last_predicted = predicted_prices[-1]
    pct_change = ((last_predicted - first_price) / (first_price + 1e-9)) * 100
    alert = build_alert(trend, commodity_title, pct_change)

    return ForecastResponse(
        commodity=commodity_title,
        market=market_title,
        currency=currency,
        unit=unit,
        horizon_days=horizon,
        forecast=points,
        trend=trend,
        alert=alert,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/compare/{commodity}", response_model=list[ForecastResponse])
def compare_markets(
    commodity: str,
    markets: str = Query(
        default="Kampala,Mbarara,Gulu",
        description="Comma-separated market names to compare"
    ),
    horizon: int = Query(default=14, ge=1, le=30),
):
    """
    Compare price forecasts for one commodity across multiple markets.
    Helps farmers decide the best market to sell in.

    Example: `/forecasts/compare/Maize?markets=Kampala,Mbarara,Kabale&horizon=14`
    """
    market_list = [m.strip().title() for m in markets.split(",") if m.strip()]
    results = []
    for mkt in market_list:
        try:
            result = get_forecast(commodity=commodity, market=mkt, horizon=horizon)
            results.append(result)
        except HTTPException:
            continue  # skip markets with no data silently

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast data available for '{commodity}' in any of the requested markets."
        )
    return results
