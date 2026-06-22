"""
AgriGuard — Price Forecast page
Calls /api/v1/forecasts/{commodity}/{market}?horizon=N
"""

import os
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="Price Forecast | AgriGuard",
    page_icon="📈",
    layout="wide",
)
st.title("📈 Crop Price Forecast")
st.caption("ML-powered price predictions up to 24 months ahead (UGX/kg)")


# ── helpers ────────────────────────────────────────────────────────────────

def api_get(path: str, params: dict = None):
    try:
        r = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


@st.cache_data(ttl=300)
def get_commodities():
    data = api_get("/api/v1/forecasts/commodities")
    return data["commodities"] if data else [
        "Maize", "Beans", "Rice", "Cassava",
        "Sorghum", "Sweet Potato", "Groundnuts", "Millet",
    ]


@st.cache_data(ttl=300)
def get_markets():
    data = api_get("/api/v1/forecasts/markets")
    return data["markets"] if data else [
        "Kampala", "Gulu", "Mbarara", "Jinja",
        "Mbale", "Lira", "Arua", "Fort Portal",
    ]


@st.cache_data(ttl=120)
def get_forecast(commodity: str, market: str, horizon: int):
    return api_get(
        f"/api/v1/forecasts/{commodity}/{market}",
        params={"horizon": horizon},
    )


@st.cache_data(ttl=120)
def get_history(commodity: str, market: str):
    return api_get(
        f"/api/v1/markets/history/{commodity}/{market}",
        params={"months": 24},
    )


# ── sidebar controls ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("Forecast Settings")
    commodities = get_commodities()
    markets     = get_markets()

    commodity = st.selectbox("Commodity", commodities)
    market    = st.selectbox("Market",    markets)
    horizon   = st.slider("Horizon (months)", 1, 24, 6)
    run       = st.button("Run Forecast", type="primary", use_container_width=True)

    st.divider()
    st.caption("Powered by XGBoost trained on WFP Uganda market data.")


# ── main area ──────────────────────────────────────────────────────────────
if run or True:   # auto-run on page load
    col_info, col_metric = st.columns([3, 1])

    forecast_data = get_forecast(commodity, market, horizon)
    history_data  = get_history(commodity, market)

    if forecast_data is None:
        st.warning(
            "⚠️ Backend not reachable. "
            f"Make sure the API is running at `{BACKEND_URL}`."
        )
        st.stop()

    forecasts = forecast_data.get("forecasts", [])
    if not forecasts:
        st.error("No forecast data returned. Check that models are trained.")
        st.stop()

    df_fc = pd.DataFrame(forecasts)
    df_fc["date"] = pd.to_datetime(
        df_fc["year"].astype(str) + "-" + df_fc["month"].astype(str).str.zfill(2) + "-01"
    )

    # ── metrics row ────────────────────────────────────────────────────────
    first_pred = df_fc["predicted_price_ugx"].iloc[0]
    last_pred  = df_fc["predicted_price_ugx"].iloc[-1]
    pct_change = (last_pred - first_pred) / (first_pred + 1e-9) * 100
    model_r2   = forecast_data.get("model_r2")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Next Month",   f"UGX {first_pred:,.0f}")
    m2.metric(f"Month {horizon}", f"UGX {last_pred:,.0f}",
              delta=f"{pct_change:+.1f}%")
    m3.metric("Horizon",      f"{horizon} months")
    m4.metric("Model R²",     f"{model_r2:.3f}" if model_r2 else "N/A")

    st.divider()

    # ── combined history + forecast chart ─────────────────────────────────
    fig = go.Figure()

    # historical line
    if history_data and history_data.get("data"):
        df_hist = pd.DataFrame(history_data["data"])
        df_hist["date"] = pd.to_datetime(df_hist["date"])
        fig.add_trace(go.Scatter(
            x=df_hist["date"], y=df_hist["price"],
            name="Historical Price",
            mode="lines",
            line=dict(color="#3498db", width=2),
        ))

    # confidence band
    fig.add_trace(go.Scatter(
        x=pd.concat([df_fc["date"], df_fc["date"][::-1]]),
        y=pd.concat([df_fc["upper_bound_ugx"], df_fc["lower_bound_ugx"][::-1]]),
        fill="toself",
        fillcolor="rgba(46,204,113,0.15)",
        line=dict(color="rgba(0,0,0,0)"),
        name="90% Confidence Band",
        showlegend=True,
    ))

    # forecast line
    fig.add_trace(go.Scatter(
        x=df_fc["date"], y=df_fc["predicted_price_ugx"],
        name="Forecast",
        mode="lines+markers",
        line=dict(color="#2ecc71", width=2.5, dash="dot"),
        marker=dict(size=7, symbol="circle"),
    ))

    fig.update_layout(
        title=f"{commodity} — {market}",
        xaxis_title="Date",
        yaxis_title="Price (UGX/kg)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left"),
        height=430,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── forecast table ─────────────────────────────────────────────────────
    with st.expander("📋 Forecast Data Table"):
        display_df = df_fc[["date", "predicted_price_ugx", "lower_bound_ugx", "upper_bound_ugx"]].copy()
        display_df.columns = ["Month", "Forecast (UGX)", "Lower Bound", "Upper Bound"]
        display_df["Month"] = display_df["Month"].dt.strftime("%b %Y")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── interpretation ─────────────────────────────────────────────────────
    direction = "rise" if pct_change > 2 else ("fall" if pct_change < -2 else "remain stable")
    st.info(
        f"**Outlook:** {commodity} prices in {market} are forecast to **{direction}** "
        f"by **{abs(pct_change):.1f}%** over the next {horizon} months. "
        f"Confidence band shows ±10% range."
    )
