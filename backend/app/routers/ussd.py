"""
AgriGuard - ussd.py
USSD gateway router for low-bandwidth farmer access.

Works with Africa's Talking USSD API (standard for Uganda/East Africa).
Farmers on basic phones (no internet) can check prices, forecasts,
and market recommendations by dialing a shortcode like *384*AGRIGUARD#

USSD Session Flow:
  CON  → session is ongoing, show next menu
  END  → session is complete, close connection

Menu Tree:
  1. Check Crop Prices
     → Enter crop name → Select market → Show price + trend
  2. Best Market to Sell
     → Enter crop name → Show ranked markets
  3. Price Forecast
     → Enter crop name → Show 7-day forecast summary
  4. Top Price Movers Today
     → Show biggest gainers/losers
  5. About AgriGuard
"""

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import PlainTextResponse
from typing import Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ussd", tags=["USSD"])

# ── Data Path ─────────────────────────────────────────────────────────────────
DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "raw", "wfp_food_prices_uga.csv"
)

# ── USSD constants ────────────────────────────────────────────────────────────
CON = "CON"   # session continues
END = "END"   # session ends

# Default markets for quick lookup
DEFAULT_MARKETS = ["Kampala", "Mbarara", "Gulu", "Kabale", "Jinja", "Mbale"]

# Max characters per USSD screen (160 is safe for most carriers)
USSD_CHAR_LIMIT = 160


# ── Data helpers (lightweight — no Prophet needed for USSD) ───────────────────

def load_data() -> pd.DataFrame:
    """Load and normalise WFP price CSV."""
    try:
        df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        return pd.DataFrame()

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
    df.rename(columns=rename_map, inplace=True)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date", "price"], inplace=True)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df.dropna(subset=["price"], inplace=True)
    df["commodity"] = df["commodity"].str.strip().str.title()
    df["market"] = df["market"].str.strip().str.title()
    return df


def get_latest_price(df: pd.DataFrame, commodity: str, market: str) -> Optional[dict]:
    """Return latest price info for a commodity-market pair."""
    subset = df[
        (df["commodity"].str.lower() == commodity.lower()) &
        (df["market"].str.lower() == market.lower())
    ].sort_values("date")

    if subset.empty:
        return None

    latest = subset.iloc[-1]
    currency = str(latest.get("currency", "UGX")) if "currency" in subset.columns else "UGX"
    unit = str(latest.get("unit", "KG")) if "unit" in subset.columns else "KG"

    # Simple trend: compare last price to 30 days ago
    cutoff = latest["date"] - timedelta(days=30)
    past = subset[subset["date"] <= cutoff]
    trend_arrow = ""
    if not past.empty:
        old_price = float(past.iloc[-1]["price"])
        new_price = float(latest["price"])
        pct = ((new_price - old_price) / (old_price + 1e-9)) * 100
        if pct > 2:
            trend_arrow = f" ▲{abs(pct):.0f}%"
        elif pct < -2:
            trend_arrow = f" ▼{abs(pct):.0f}%"
        else:
            trend_arrow = " →stable"

    return {
        "price": round(float(latest["price"]), 0),
        "currency": currency,
        "unit": unit,
        "date": latest["date"].strftime("%d %b %Y"),
        "trend": trend_arrow,
    }


def get_market_ranking(df: pd.DataFrame, commodity: str) -> list[dict]:
    """Rank all markets by latest price for a commodity (highest first)."""
    markets = df[df["commodity"].str.lower() == commodity.lower()]["market"].unique()
    results = []
    for mkt in markets:
        record = get_latest_price(df, commodity, mkt)
        if record:
            results.append({"market": mkt, **record})
    return sorted(results, key=lambda x: x["price"], reverse=True)


def get_simple_forecast(df: pd.DataFrame, commodity: str, horizon: int = 7) -> dict:
    """
    Lightweight linear forecast for USSD — no Prophet dependency.
    Returns predicted direction and estimated price in N days.
    """
    subset = df[
        df["commodity"].str.lower() == commodity.lower()
    ].sort_values("date").tail(24)

    if len(subset) < 4:
        return {"available": False}

    prices = subset["price"].values
    x = np.arange(len(prices))
    slope, intercept = np.polyfit(x, prices, 1)
    future_price = intercept + slope * (len(prices) + horizon)
    current_price = prices[-1]
    pct_change = ((future_price - current_price) / (current_price + 1e-9)) * 100

    currency = str(subset.iloc[-1].get("currency", "UGX")) if "currency" in subset.columns else "UGX"
    unit = str(subset.iloc[-1].get("unit", "KG")) if "unit" in subset.columns else "KG"

    if pct_change > 3:
        direction = f"RISE to ~{currency} {max(future_price,0):,.0f}/{unit}"
        advice = "Consider waiting to sell."
    elif pct_change < -3:
        direction = f"FALL to ~{currency} {max(future_price,0):,.0f}/{unit}"
        advice = "Sell soon for better price."
    else:
        direction = "stay STABLE"
        advice = "Good time to sell."

    return {
        "available": True,
        "current_price": round(float(current_price), 0),
        "direction": direction,
        "pct_change": round(pct_change, 1),
        "advice": advice,
        "currency": currency,
        "unit": unit,
    }


def get_top_movers(df: pd.DataFrame, top_n: int = 3) -> dict:
    """Get top price gainers and losers over the last 30 days for USSD display."""
    latest_date = df["date"].max()
    cutoff = latest_date - timedelta(days=30)

    movers = []
    for (commodity, market), group in df.groupby(["commodity", "market"]):
        group = group.sort_values("date")
        recent = group[group["date"] >= cutoff]
        past = group[group["date"] < cutoff]
        if recent.empty or past.empty:
            continue
        latest_p = float(recent.iloc[-1]["price"])
        prev_p = float(past.iloc[-1]["price"])
        pct = ((latest_p - prev_p) / (prev_p + 1e-9)) * 100
        movers.append({"commodity": commodity, "market": market, "pct": round(pct, 1)})

    if not movers:
        return {"gainers": [], "losers": []}

    movers_df = pd.DataFrame(movers)
    gainers = movers_df.nlargest(top_n, "pct").to_dict(orient="records")
    losers = movers_df.nsmallest(top_n, "pct").to_dict(orient="records")
    return {"gainers": gainers, "losers": losers}


def fuzzy_match_commodity(df: pd.DataFrame, user_input: str) -> Optional[str]:
    """
    Find the best matching commodity name from user's typed input.
    Handles partial matches (e.g. 'maiz' → 'Maize', 'bean' → 'Beans').
    """
    user_clean = user_input.strip().lower()
    all_commodities = df["commodity"].unique()

    # Exact match first
    for c in all_commodities:
        if c.lower() == user_clean:
            return c

    # Starts-with match
    for c in all_commodities:
        if c.lower().startswith(user_clean):
            return c

    # Contains match
    for c in all_commodities:
        if user_clean in c.lower():
            return c

    return None


def truncate(text: str, limit: int = USSD_CHAR_LIMIT) -> str:
    """Ensure USSD response stays within character limit."""
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


# ── Session State Parser ──────────────────────────────────────────────────────

def parse_session(text: str) -> list[str]:
    """
    Africa's Talking sends the full input chain as star-separated values.
    e.g. "1*Maize*2" → ["1", "Maize", "2"]
    Empty string means session just started.
    """
    if not text or text.strip() == "":
        return []
    return [t.strip() for t in text.split("*") if t.strip() != ""]


# ── Main USSD Endpoint ────────────────────────────────────────────────────────

@router.post("", response_class=PlainTextResponse)
@router.post("/", response_class=PlainTextResponse)
async def ussd_handler(
    sessionId: str = Form(...),
    serviceCode: str = Form(...),
    phoneNumber: str = Form(...),
    text: str = Form(default=""),
):
    """
    Africa's Talking USSD callback endpoint.

    Receives POST with form fields:
    - sessionId: unique session identifier
    - serviceCode: the shortcode dialed
    - phoneNumber: caller's number
    - text: full input chain (star-separated)

    Returns plain text starting with CON (continue) or END (terminate).
    """
    df = load_data()
    inputs = parse_session(text)
    depth = len(inputs)

    logger.info(f"USSD | session={sessionId} | phone={phoneNumber} | text='{text}' | depth={depth}")

    # ── Level 0: Main Menu ────────────────────────────────────────────────────
    if depth == 0:
        response = (
            f"{CON} AgriGuard\n"
            "Uganda Farm Prices\n"
            "──────────────\n"
            "1. Check Crop Price\n"
            "2. Best Market to Sell\n"
            "3. Price Forecast\n"
            "4. Top Movers Today\n"
            "5. About AgriGuard"
        )
        return truncate(response)

    choice = inputs[0]

    # ══════════════════════════════════════════════════════════════════════════
    # OPTION 1 — Check Crop Price
    # ══════════════════════════════════════════════════════════════════════════
    if choice == "1":

        # Step 1 → Ask for crop name
        if depth == 1:
            return truncate(f"{CON} Check Crop Price\nEnter crop name:\n(e.g. Maize, Beans, Tomatoes)")

        # Step 2 → Ask for market
        if depth == 2:
            crop_input = inputs[1]
            commodity = fuzzy_match_commodity(df, crop_input)
            if not commodity:
                return truncate(f"{END} Sorry, '{crop_input}' not found.\nTry: Maize, Beans, Tomatoes, Cassava")

            market_menu = "\n".join(
                [f"{i+1}. {m}" for i, m in enumerate(DEFAULT_MARKETS)]
            )
            return truncate(f"{CON} Select market:\n{market_menu}\n7. Other (type name)")

        # Step 3 → Show price
        if depth == 3:
            crop_input = inputs[1]
            market_input = inputs[2]
            commodity = fuzzy_match_commodity(df, crop_input)

            # Resolve market: number or typed name
            if market_input.isdigit():
                idx = int(market_input) - 1
                if 0 <= idx < len(DEFAULT_MARKETS):
                    market = DEFAULT_MARKETS[idx]
                else:
                    return truncate(f"{END} Invalid market selection.")
            else:
                market = market_input.strip().title()

            if not commodity:
                return truncate(f"{END} Crop not found. Please try again.")

            record = get_latest_price(df, commodity, market)
            if not record:
                return truncate(
                    f"{END} No price data for {commodity} in {market}.\n"
                    f"Try another market."
                )

            return truncate(
                f"{END} {commodity} | {market}\n"
                f"Price: {record['currency']} {record['price']:,.0f}/{record['unit']}\n"
                f"Trend: {record['trend']}\n"
                f"Date: {record['date']}\n"
                f"AgriGuard - Know Before You Sell"
            )

        # Step 4+ → Other market typed
        if depth == 4 and inputs[2] == "7":
            crop_input = inputs[1]
            market = inputs[3].strip().title()
            commodity = fuzzy_match_commodity(df, crop_input)

            if not commodity:
                return truncate(f"{END} Crop not found.")

            record = get_latest_price(df, commodity, market)
            if not record:
                return truncate(f"{END} No data for {commodity} in {market}.")

            return truncate(
                f"{END} {commodity} | {market}\n"
                f"Price: {record['currency']} {record['price']:,.0f}/{record['unit']}\n"
                f"Trend: {record['trend']}\n"
                f"Date: {record['date']}"
            )

    # ══════════════════════════════════════════════════════════════════════════
    # OPTION 2 — Best Market to Sell
    # ══════════════════════════════════════════════════════════════════════════
    elif choice == "2":

        if depth == 1:
            return truncate(f"{CON} Best Market to Sell\nEnter crop name:\n(e.g. Maize, Beans)")

        if depth == 2:
            crop_input = inputs[1]
            commodity = fuzzy_match_commodity(df, crop_input)

            if not commodity:
                return truncate(f"{END} Crop '{crop_input}' not found.\nTry: Maize, Beans, Tomatoes")

            ranking = get_market_ranking(df, commodity)
            if not ranking:
                return truncate(f"{END} No market data for {commodity}.")

            # Show top 4 markets ranked by price
            top = ranking[:4]
            lines = [f"{CON} {commodity} - Best Markets:\n"]
            for i, r in enumerate(top):
                marker = " ★" if i == 0 else ""
                lines.append(
                    f"{i+1}. {r['market']}: {r['currency']} {r['price']:,.0f}{r['trend']}{marker}"
                )
            lines.append(f"\nBest: {top[0]['market']}")
            if len(ranking) > 1:
                lines.append(f"Avoid: {ranking[-1]['market']}")
            lines.append("\n0. Back to Menu")

            return truncate("\n".join(lines))

        if depth == 3 and inputs[2] == "0":
            # Back to main menu
            return truncate(
                f"{CON} AgriGuard\n"
                "1. Check Crop Price\n"
                "2. Best Market to Sell\n"
                "3. Price Forecast\n"
                "4. Top Movers Today\n"
                "5. About AgriGuard"
            )

    # ══════════════════════════════════════════════════════════════════════════
    # OPTION 3 — Price Forecast
    # ══════════════════════════════════════════════════════════════════════════
    elif choice == "3":

        if depth == 1:
            return truncate(f"{CON} Price Forecast (7 days)\nEnter crop name:\n(e.g. Maize, Beans)")

        if depth == 2:
            crop_input = inputs[1]
            commodity = fuzzy_match_commodity(df, crop_input)

            if not commodity:
                return truncate(f"{END} Crop '{crop_input}' not found.")

            fc = get_simple_forecast(df, commodity, horizon=7)

            if not fc["available"]:
                return truncate(f"{END} Not enough data to forecast {commodity}.")

            direction_icon = "📈" if fc["pct_change"] > 0 else "📉" if fc["pct_change"] < 0 else "→"

            return truncate(
                f"{END} {commodity} - 7 Day Forecast\n"
                f"Now: {fc['currency']} {fc['current_price']:,.0f}/{fc['unit']}\n"
                f"Expected to {fc['direction']}\n"
                f"Change: {fc['pct_change']:+.1f}%\n"
                f"Advice: {fc['advice']}\n"
                f"AgriGuard Forecast"
            )

    # ══════════════════════════════════════════════════════════════════════════
    # OPTION 4 — Top Movers Today
    # ══════════════════════════════════════════════════════════════════════════
    elif choice == "4":

        if depth == 1:
            movers = get_top_movers(df, top_n=3)

            if not movers["gainers"] and not movers["losers"]:
                return truncate(f"{END} No mover data available today.")

            lines = [f"{CON} Top Movers (30 days)\n"]

            if movers["gainers"]:
                lines.append("RISING:")
                for g in movers["gainers"]:
                    lines.append(f"▲ {g['commodity']} ({g['market']}): +{g['pct']}%")

            if movers["losers"]:
                lines.append("\nFALLING:")
                for l in movers["losers"]:
                    lines.append(f"▼ {l['commodity']} ({l['market']}): {l['pct']}%")

            lines.append("\n0. Main Menu")
            return truncate("\n".join(lines))

        if depth == 2 and inputs[1] == "0":
            return truncate(
                f"{CON} AgriGuard\n"
                "1. Check Crop Price\n"
                "2. Best Market to Sell\n"
                "3. Price Forecast\n"
                "4. Top Movers Today\n"
                "5. About AgriGuard"
            )

    # ══════════════════════════════════════════════════════════════════════════
    # OPTION 5 — About AgriGuard
    # ══════════════════════════════════════════════════════════════════════════
    elif choice == "5":
        return truncate(
            f"{END} AgriGuard\n"
            "Agricultural Intelligence\nfor Ugandan Farmers.\n\n"
            "Real-time prices.\nMarket comparisons.\nPrice forecasts.\n\n"
            "Free service.\nNo internet needed.\n"
            "agriguardai.com"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Invalid input
    # ══════════════════════════════════════════════════════════════════════════
    return truncate(
        f"{END} Invalid input. Please dial again and select 1-5."
    )


# ── Test / Simulator Endpoint (dev only) ─────────────────────────────────────

@router.get("/simulate", response_class=PlainTextResponse)
async def simulate_ussd(
    text: str = "",
    phone: str = "+256700000000",
):
    """
    DEV ONLY — Simulate a USSD session in the browser without a real carrier.
    Pass the star-separated input chain as ?text=1*Maize*1

    Examples:
      /ussd/simulate?text=           → main menu
      /ussd/simulate?text=1          → check price: enter crop
      /ussd/simulate?text=1*Maize*1  → Maize price in Kampala
      /ussd/simulate?text=2*Beans    → best market for Beans
      /ussd/simulate?text=3*Maize    → 7-day forecast for Maize
      /ussd/simulate?text=4          → top movers
    """
    return await ussd_handler(
        sessionId="SIM-DEV-001",
        serviceCode="*384#",
        phoneNumber=phone,
        text=text,
    )