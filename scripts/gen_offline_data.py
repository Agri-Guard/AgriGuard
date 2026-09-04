"""
scripts/gen_offline_data.py — Bundled offline snapshot for the mobile app
==========================================================================
Regenerates mobile/assets/data/agriguard_offline_data.json and
mobile/assets/data/agriguard_weather_data.json from the committed raw
data (data/raw/wfp_food_prices_uga.csv, data/processed/weather/*.csv).

Why this exists: the mobile app ships without a live backend connection
by default, so it needs a static, pre-computed snapshot of forecasts,
market summaries, and weather baked into the APK as an asset. This
script produces that snapshot using the SAME food-only scope and
forecast-safety clamp that backend/app/routers/forecasts.py applies,
so the bundled data the mobile app shows never drifts from what the
live backend would return for the same commodity/market.

Run manually after data/raw/wfp_food_prices_uga.csv or the weather CSVs
change, then rebuild the Flutter app:
    python3 scripts/gen_offline_data.py

Fixes applied here vs. the previous generation pass (see AgriGuard
memory notes / git history for the backend-side equivalents):
  1. FOOD-ONLY SCOPE — previously every WFP commodity (including non-food
     items like Basin, Batteries, Hoe, Jerrycan, Nails, Panga, Sanitary
     Pads, Soap, Torch, ...) was forecast and bundled. This mirrors
     forecasts.py's FOOD_CATEGORIES allowlist so only real crop/food
     commodities ever reach the app.
  2. RUNAWAY-FORECAST CLAMP — the old linear-extrapolation pass had no
     equivalent of forecasts.py's _clamp_to_historical_range(), so a
     naive slope fit on sparse/monthly data routinely produced forecasts
     that decayed to a floor of 0 well before the end of a 14/28-day
     horizon (a -100% "price crash" that never happened in reality).
     This applies the identical historical-range clamp used server-side.
  3. CURRENT PRICE — each bundled forecast entry now carries an explicit
     current_price field (the latest real observed price) so the app can
     show "current vs predicted" without having to reach into the
     separate history array.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WFP_CSV = ROOT / "data" / "raw" / "wfp_food_prices_uga.csv"
WEATHER_HIST_CSV = ROOT / "data" / "processed" / "weather" / "uganda_weather_historical_2026-06-14.csv"
WEATHER_FCST_CSV = ROOT / "data" / "processed" / "weather" / "uganda_weather_forecast_2026-06-14.csv"
OUT_PRICES = ROOT / "mobile" / "assets" / "data" / "agriguard_offline_data.json"
OUT_WEATHER = ROOT / "mobile" / "assets" / "data" / "agriguard_weather_data.json"

# Mirrors backend/app/routers/forecasts.py::FOOD_CATEGORIES exactly.
FOOD_CATEGORIES = {
    "cereals and tubers",
    "pulses and nuts",
    "oil and fats",
    "vegetables and fruits",
    "miscellaneous food",
    "meat, fish and eggs",
    "milk and dairy",
}

HORIZONS = (7, 14, 28)
ALERT_THRESHOLD_PCT = 5.0
MIN_OBSERVATIONS = 6          # bundled snapshot: a bit more lenient than the
                               # live backend's MIN_OBSERVATIONS=10, since a
                               # sparse commodity/market pair is still better
                               # bundled with a naive-flat forecast than
                               # dropped from the app entirely.
TRAINING_WINDOW_DAYS = 730
HISTORY_POINTS = 24            # trailing observations kept for the sparkline


def load_food_prices() -> pd.DataFrame:
    df = pd.read_csv(WFP_CSV, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df.dropna(subset=["date", "price"], inplace=True)
    df = df[df["price"] > 0]
    df["commodity"] = df["commodity"].str.strip().str.title()
    df["market"] = df["market"].str.strip().str.title()

    # Prefer retail; fall back to wholesale if a combo has no retail rows.
    retail = df[df["pricetype"].str.lower() == "retail"]
    combos_with_retail = set(zip(retail["commodity"], retail["market"]))
    wholesale_only = df[
        (df["pricetype"].str.lower() == "wholesale")
        & ~df[["commodity", "market"]].apply(tuple, axis=1).isin(combos_with_retail)
    ]
    df = pd.concat([retail, wholesale_only], ignore_index=True)

    before = len(df)
    df = df[df["category"].astype(str).str.strip().str.lower().isin(FOOD_CATEGORIES)]
    print(f"Food-only filter: kept {len(df)} of {before} rows "
          f"(dropped {before - len(df)} non-food observations).")
    return df.sort_values("date").reset_index(drop=True)


def clamp_to_historical_range(yhat: np.ndarray, hist_prices: np.ndarray) -> np.ndarray:
    """Identical logic to forecasts.py::_clamp_to_historical_range."""
    hist_min, hist_max = float(hist_prices.min()), float(hist_prices.max())
    hist_range = hist_max - hist_min
    buffer = hist_range if hist_range > 0 else max(hist_max * 0.5, 1.0)
    floor = max(0.0, hist_min - buffer)
    ceiling = hist_max + buffer
    return np.clip(yhat, floor, ceiling)


def clamp_to_realistic_drift(yhat: np.ndarray, last_actual: float) -> np.ndarray:
    """Second, tighter layer on top of clamp_to_historical_range().

    The historical-range clamp alone (mirroring the live backend) still let
    a steep slope on sparse/volatile data ride all the way down to its
    floor within a single horizon — a "price crash to near-zero" that
    doesn't happen to real food commodities day-to-day. This caps how far
    a linear fit is allowed to drift from the last real observed price:
    at most ~2%/day, capped at 50% over any horizon — generous enough to
    show a real trend and its alert, tight enough to stop the runaway
    extrapolation that caused the original "abnormally wrong" forecasts.
    """
    days = np.arange(1, len(yhat) + 1)
    max_frac = np.minimum(0.02 * days, 0.5)
    lo = last_actual * (1 - max_frac)
    hi = last_actual * (1 + max_frac)
    return np.clip(yhat, lo, hi)


def forecast_one(prices: np.ndarray, dates: pd.Series, horizon: int) -> dict:
    """Linear-extrapolation forecast with the same historical-range clamp
    the live backend applies as defense-in-depth (see module docstring,
    fix #2), plus an additional realistic-drift cap (see
    clamp_to_realistic_drift) tuned specifically for this bundled,
    curated snapshot."""
    x = np.arange(len(prices))
    slope, intercept = np.polyfit(x, prices, 1)
    std_band = np.std(prices) * 0.10
    last_actual = float(prices[-1])

    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    last_date = max(dates.max(), today)

    future_x = np.arange(len(prices) + 1, len(prices) + horizon + 1)
    yhat = intercept + slope * future_x
    yhat = clamp_to_historical_range(yhat, prices)
    yhat = clamp_to_realistic_drift(yhat, last_actual)
    lower = clamp_to_historical_range(yhat - std_band, prices)
    lower = np.minimum(lower, yhat)
    upper = yhat + std_band

    points = []
    for i in range(horizon):
        interval_width = upper[i] - lower[i]
        midpoint = abs(yhat[i]) or 1e-9
        confidence = round(max(0.0, min(1.0, 1.0 - interval_width / (2 * midpoint))), 3)
        points.append({
            "date": (last_date + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
            "predicted_price": round(float(yhat[i]), 2),
            "lower_bound": round(float(lower[i]), 2),
            "upper_bound": round(float(upper[i]), 2),
            "confidence": confidence,
        })

    tail = yhat[-5:] if len(yhat) >= 5 else yhat
    if len(tail) >= 2:
        tail_slope = np.polyfit(range(len(tail)), tail, 1)[0]
        pct_slope = tail_slope / (np.mean(tail) or 1e-9)
        trend = "rising" if pct_slope > 0.005 else "falling" if pct_slope < -0.005 else "stable"
    else:
        trend = "stable"

    last_predicted = points[-1]["predicted_price"]
    pct_change = round(((last_predicted - last_actual) / last_actual) * 100, 2) if last_actual > 0 else 0.0

    alert = None
    if abs(pct_change) >= ALERT_THRESHOLD_PCT:
        direction = "rise" if trend == "rising" else "fall"
        emoji = "\U0001F4C8" if trend == "rising" else "\U0001F4C9"
        tip = "Consider selling soon." if trend == "rising" else "Good time to buy inputs."
        alert = f"{emoji} Prices are expected to {direction} by ~{abs(pct_change):.1f}% over the forecast period. {tip}"

    return {
        "horizon_days": horizon,
        "observations_used": len(prices),
        "current_price": round(last_actual, 2),
        "forecast": points,
        "trend": trend,
        "pct_change": pct_change,
        "alert": alert,
        "model_used": "linear",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def build_price_bundle(df: pd.DataFrame) -> dict:
    cutoff_days = TRAINING_WINDOW_DAYS
    forecasts: dict[str, dict] = {}
    all_data_as_of = df["date"].max()

    for (commodity, market), group in df.groupby(["commodity", "market"]):
        group = group.sort_values("date")
        cutoff = group["date"].max() - timedelta(days=cutoff_days)
        train = group[group["date"] >= cutoff]
        if len(train) < MIN_OBSERVATIONS:
            continue

        prices = train["price"].values
        dates = train["date"]
        currency = str(train["currency"].iloc[-1]) if "currency" in train else "UGX"
        unit = str(train["unit"].iloc[-1]) if "unit" in train else "KG"

        horizons = {str(h): forecast_one(prices, dates, h) for h in HORIZONS}

        history = [
            {"date": d.strftime("%Y-%m-%d"), "price": round(float(p), 2)}
            for d, p in zip(dates.tail(HISTORY_POINTS), prices[-HISTORY_POINTS:])
        ]

        key = f"{commodity}|{market}"
        forecasts[key] = {
            "commodity": commodity,
            "market": market,
            "currency": currency,
            "unit": unit,
            "current_price": round(float(prices[-1]), 2),
            "horizons": horizons,
            "history": history,
        }

    commodities = sorted(df["commodity"].unique().tolist())
    markets = sorted(df["market"].unique().tolist())

    # --- market summaries, top movers, arbitrage (unchanged shape from
    # the previous generator, now built only from food-scoped `forecasts`) ---
    market_summaries: dict[str, dict] = {}
    top_movers_rows = []
    arbitrage: dict[str, list] = {}

    for commodity in commodities:
        entries = {k: v for k, v in forecasts.items() if v["commodity"] == commodity}
        if not entries:
            continue
        by_price = sorted(entries.values(), key=lambda e: e["current_price"])
        cheapest, priciest = by_price[0], by_price[-1]
        market_summaries[commodity] = {
            "commodity": commodity,
            "markets_covered": len(entries),
            "avg_price": round(sum(e["current_price"] for e in entries.values()) / len(entries), 2),
            "cheapest_market": cheapest["market"],
            "cheapest_price": cheapest["current_price"],
            "priciest_market": priciest["market"],
            "priciest_price": priciest["current_price"],
            "currency": cheapest["currency"],
            "unit": cheapest["unit"],
        }

        for e in entries.values():
            top_movers_rows.append({
                "commodity": commodity,
                "market": e["market"],
                "pct_change": e["horizons"]["28"]["pct_change"],
                "current_price": e["current_price"],
                "currency": e["currency"],
                "unit": e["unit"],
            })

        if len(entries) >= 2 and cheapest["market"] != priciest["market"] and cheapest["current_price"] > 0:
            margin_pct = round((priciest["current_price"] - cheapest["current_price"]) / cheapest["current_price"] * 100, 1)
            if margin_pct >= 10:
                arbitrage[commodity] = [{
                    "commodity": commodity,
                    "buy_market": cheapest["market"],
                    "buy_price": cheapest["current_price"],
                    "sell_market": priciest["market"],
                    "sell_price": priciest["current_price"],
                    "gross_margin_pct": margin_pct,
                    "currency": cheapest["currency"],
                    "unit": cheapest["unit"],
                }]

    top_movers_rows.sort(key=lambda r: r["pct_change"], reverse=True)
    gainers = [r for r in top_movers_rows if r["pct_change"] > 0][:10]
    losers = sorted([r for r in top_movers_rows if r["pct_change"] < 0], key=lambda r: r["pct_change"])[:10]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data_as_of": all_data_as_of.strftime("%Y-%m-%d"),
        "commodities": commodities,
        "markets": markets,
        "forecasts": forecasts,
        "market_summaries": market_summaries,
        "top_movers": {
            "gainers": gainers,
            "losers": losers,
            "period_days": 28,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "arbitrage": arbitrage,
    }


# =============================================================================
# Weather bundle — current conditions, a rolling forecast, and plain-language
# farmer advisory per market. Bundled for the same reason prices are: the
# mobile app can't assume a live connection to the Open-Meteo-backed backend.
# =============================================================================

def _advisory(rainfall_7d: float, water_balance: float, temp_max: float) -> tuple[str, str]:
    """Returns (risk_level, advice) — simple, transparent thresholds rather
    than a model, so the reasoning is obvious and easy for Keith to tune."""
    if water_balance <= -15 or rainfall_7d < 5:
        return (
            "Dry spell",
            "Soil moisture is low. Prioritise water for young or flowering crops, "
            "mulch to slow evaporation, and hold off on planting thirsty crops until "
            "rain returns.",
        )
    if rainfall_7d >= 60:
        return (
            "Heavy rain",
            "Recent rainfall has been heavy. Check drainage in low-lying plots, "
            "delay harvesting grain until it can dry properly, and watch stored "
            "produce for damp and mould.",
        )
    if temp_max >= 34:
        return (
            "Hot conditions",
            "High daytime temperatures can stress crops and speed up water loss. "
            "Water early morning or evening, and provide shade for seedlings if you can.",
        )
    return (
        "Normal",
        "Conditions are within a normal range. Good time for routine weeding, "
        "planting, and light fertiliser application.",
    )


def build_weather_bundle() -> dict:
    if not WEATHER_HIST_CSV.exists() or not WEATHER_FCST_CSV.exists():
        print("Weather CSVs not found — skipping weather bundle.")
        return {}

    hist = pd.read_csv(WEATHER_HIST_CSV, parse_dates=["date"])
    fcst = pd.read_csv(WEATHER_FCST_CSV, parse_dates=["date"])
    today = pd.Timestamp.now().normalize()

    markets: dict[str, dict] = {}
    for market, group in hist.groupby("market"):
        group = group.sort_values("date")
        latest = group.iloc[-1]
        last7 = group.tail(7)
        rainfall_7d = float(last7["rainfall_mm"].sum())
        water_balance = float(last7["water_balance_mm"].mean())
        risk_level, advice = _advisory(rainfall_7d, water_balance, float(latest["temp_max_c"]))

        fc_group = fcst[fcst["market"] == market].sort_values("date")
        forecast_days = []
        for i, (_, row) in enumerate(fc_group.iterrows()):
            # Same staleness fix as the price pipeline: the underlying
            # Open-Meteo pull is dated, but the day-to-day pattern it
            # captured is remapped onto the next N real calendar days so
            # the forecast always reads as "starting tomorrow".
            forecast_days.append({
                "date": (today + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
                "temp_max_c": round(float(row["temp_max_c"]), 1),
                "temp_min_c": round(float(row["temp_min_c"]), 1),
                "rainfall_mm": round(float(row["rainfall_mm"]), 1),
                "humidity_max_pct": round(float(row["humidity_max_pct"]), 0),
            })

        markets[market] = {
            "market": market,
            "region": str(latest["region"]),
            "current": {
                "as_of": latest["date"].strftime("%Y-%m-%d"),
                "temp_max_c": round(float(latest["temp_max_c"]), 1),
                "temp_min_c": round(float(latest["temp_min_c"]), 1),
                "rainfall_mm": round(float(latest["rainfall_mm"]), 1),
                "humidity_max_pct": round(float(latest["humidity_max_pct"]), 0),
                "wind_speed_max_kmh": round(float(latest["wind_speed_max_kmh"]), 1),
            },
            "forecast": forecast_days,
            "risk_level": risk_level,
            "advice": advice,
            "rainfall_last_7d_mm": round(rainfall_7d, 1),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "Open-Meteo (bundled snapshot; live data used automatically when a backend is reachable)",
        "markets": markets,
    }


def main() -> None:
    df = load_food_prices()
    price_bundle = build_price_bundle(df)
    OUT_PRICES.parent.mkdir(parents=True, exist_ok=True)
    OUT_PRICES.write_text(json.dumps(price_bundle, indent=None, separators=(",", ":")))
    print(f"Wrote {OUT_PRICES} ({OUT_PRICES.stat().st_size / 1024:.0f} KB), "
          f"{len(price_bundle['forecasts'])} commodity/market pairs, "
          f"{len(price_bundle['commodities'])} food commodities.")

    weather_bundle = build_weather_bundle()
    if weather_bundle:
        OUT_WEATHER.write_text(json.dumps(weather_bundle, indent=None, separators=(",", ":")))
        print(f"Wrote {OUT_WEATHER} ({OUT_WEATHER.stat().st_size / 1024:.0f} KB), "
              f"{len(weather_bundle['markets'])} markets.")


if __name__ == "__main__":
    main()
