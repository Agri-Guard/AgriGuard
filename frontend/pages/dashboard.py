"""
AgriGuard Dashboard — Backend-Connected + Weather Insights
==========================================================
Fully wired to the FastAPI backend:
  POST /api/v1/predict           → Price Prediction tab
  POST /api/v1/validate          → Fake Input Detector tab
  GET  /forecasts/{commodity}    → Forecast chart (Prophet/XGBoost)
  GET  /forecasts/history/{c}    → Historical sparkline
  GET  /forecasts/commodities    → Dynamic crop/market dropdowns
  GET  /markets/national-summary → National overview table
  GET  /markets/movers           → Price gainers/losers
  GET  /markets/summary/{c}      → Cross-market comparison
  GET  /health                   → Backend status indicator

Weather data: Open-Meteo API (free, no API key required)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AgriGuard Dashboard",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM STYLES
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }

    .metric-card {
        background: linear-gradient(135deg, #0d1f0d 0%, #1a2e1a 100%);
        border: 1px solid #00cc6633;
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 8px;
    }
    .metric-val  { font-size: 1.9rem; font-weight: 700; color: #00cc66; }
    .metric-lbl  { font-size: 0.82rem; color: #aaa; text-transform: uppercase; letter-spacing: .08em; }
    .trend-up    { color: #00cc66; }
    .trend-down  { color: #ff4c4c; }
    .trend-stable{ color: #f0a500; }
    .alert-high  { background:#3d0000; border-left:4px solid #ff4c4c; padding:8px 12px; border-radius:4px; margin-bottom:6px; }
    .alert-med   { background:#2d1a00; border-left:4px solid #f0a500; padding:8px 12px; border-radius:4px; margin-bottom:6px; }
    .alert-low   { background:#002d1a; border-left:4px solid #00cc66; padding:8px 12px; border-radius:4px; margin-bottom:6px; }
    .status-dot-ok  { display:inline-block; width:10px; height:10px; border-radius:50%; background:#00cc66; margin-right:6px; }
    .status-dot-err { display:inline-block; width:10px; height:10px; border-radius:50%; background:#ff4c4c; margin-right:6px; }
    .weather-card {
        background: linear-gradient(135deg, #0d1a2e 0%, #1a2540 100%);
        border: 1px solid #1E90FF33;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 8px;
    }
    .weather-risk-high   { color: #ff4c4c; font-weight: 700; }
    .weather-risk-med    { color: #f0a500; font-weight: 700; }
    .weather-risk-low    { color: #00cc66; font-weight: 700; }
    .weather-advice      { color: #cce8ff; font-size: 0.9rem; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# BACKEND URL (configurable via sidebar)
# ─────────────────────────────────────────────
DEFAULT_BASE = "http://localhost:8000"

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def api(method: str, path: str, base: str, **kwargs):
    """Thin wrapper — returns (data_or_None, error_str_or_None)."""
    url = f"{base.rstrip('/')}{path}"
    try:
        r = requests.request(method, url, timeout=15, **kwargs)
        if r.status_code in (200, 201):
            return r.json(), None
        return None, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach backend — is it running?"
    except Exception as exc:
        return None, str(exc)


def trend_html(t: str) -> str:
    icons = {"rising": "📈", "falling": "📉", "stable": "➡️", "up": "📈", "down": "📉"}
    css   = {"rising": "trend-up", "falling": "trend-down", "stable": "trend-stable",
             "up": "trend-up", "down": "trend-down"}
    icon  = icons.get(t, "")
    cls   = css.get(t, "trend-stable")
    return f'<span class="{cls}">{icon} {t.title()}</span>'


def ugx(v) -> str:
    return f"UGX {v:,.0f}" if v else "—"


# ─────────────────────────────────────────────
# WEATHER HELPER
# ─────────────────────────────────────────────

# Approximate coordinates for major Ugandan markets
MARKET_COORDS = {
    "Kampala": (0.3476,  32.5825),
    "Mbarara": (-0.6064, 30.6485),
    "Gulu":    (2.7724,  32.2903),
    "Mbale":   (1.0778,  34.1778),
    "Jinja":   (0.4524,  33.2033),
    "Lira":    (2.2489,  32.8999),
    "Masaka":  (-0.3411, 31.7384),
    "Arua":    (3.0200,  30.9114),
    "Fort Portal": (0.6606, 30.2749),
    "Soroti":  (1.7152,  33.6116),
}

# WMO weather code → human label
WMO_DESCRIPTIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Heavy thunderstorm + hail",
}

# Per-crop risk thresholds and advice templates
CROP_WEATHER_PROFILES = {
    "maize": {
        "heat_thresh": 32,
        "heat_action": "Irrigate twice daily — maize silking stage is heat-sensitive. Prioritise morning watering.",
        "rain_high_thresh": 15,
        "rain_high_action": "Delay harvesting. Excess moisture promotes aflatoxin mould. Apply fungicide if cobs are exposed.",
        "drought_action": "Apply furrow irrigation. Maize at tasseling stage needs ≥5mm/day — consider drip lines.",
        "good_action": "Good conditions for maize. Monitor for stalk borers after rains.",
    },
    "beans": {
        "heat_thresh": 30,
        "heat_action": "Shade young bean plants if possible. Heat above 30°C causes pod drop.",
        "rain_high_thresh": 12,
        "rain_high_action": "Watch for bean rust and anthracnose. Improve drainage in plots. Spray copper-based fungicide.",
        "drought_action": "Beans are drought-tolerant but pod fill needs moisture — irrigate lightly every 2–3 days.",
        "good_action": "Ideal window for bean planting or pod development. No immediate risk.",
    },
    "cassava": {
        "heat_thresh": 35,
        "heat_action": "Cassava tolerates heat well but wilting at 35°C+ damages yield. Light irrigation if possible.",
        "rain_high_thresh": 20,
        "rain_high_action": "Heavy rain risks root rot in waterlogged soil. Mound cassava rows higher to improve drainage.",
        "drought_action": "Cassava is drought-resilient; no irrigation needed unless crop is under 3 months old.",
        "good_action": "Excellent cassava conditions. Good window for planting cuttings.",
    },
    "coffee": {
        "heat_thresh": 30,
        "heat_action": "Coffee suffers above 30°C — risk of berry borer increase. Increase shade tree density.",
        "rain_high_thresh": 10,
        "rain_high_action": "Coffee berry disease (CBD) risk is high in wet conditions. Spray copper fungicide. Pick ripe berries promptly.",
        "drought_action": "Coffee needs consistent moisture. Mulch thickly around trees. Irrigate if dry season exceeds 3 weeks.",
        "good_action": "Good coffee conditions. Monitor for leaf rust during flowering.",
    },
    "matooke": {
        "heat_thresh": 32,
        "heat_action": "Banana/matooke needs moisture in heat — water the root zone daily. Mulch with dry leaves.",
        "rain_high_thresh": 18,
        "rain_high_action": "High rain risk: Black Sigatoka fungal spread. Remove infected leaves. Apply systemic fungicide.",
        "drought_action": "Matooke is water-hungry. Irrigate every 2 days. Severe drought causes pseudostem collapse.",
        "good_action": "Favorable matooke weather. Good period for bunch harvesting and suckers management.",
    },
}

# Generic fallback for crops not in profile
DEFAULT_PROFILE = {
    "heat_thresh": 32,
    "heat_action": "High temperatures detected — irrigate crops and provide shade where possible.",
    "rain_high_thresh": 15,
    "rain_high_action": "Heavy rain forecast — delay planting and check for waterlogging and fungal risks.",
    "drought_action": "Dry conditions — prioritize irrigation and apply mulch to retain soil moisture.",
    "good_action": "Favorable conditions for crop activities.",
}


def classify_weather(rain_mm: float, tmax: float, tmin: float, wmo_code: int, crop: str):
    """Return (risk_label, risk_level, actionable_advice) for a single day."""
    profile = CROP_WEATHER_PROFILES.get(crop.lower(), DEFAULT_PROFILE)

    # Flood / very heavy rain
    if rain_mm > profile["rain_high_thresh"] * 1.5 or wmo_code in (65, 82, 95, 96, 99):
        return "🔴 Flood / Severe Storm", "high", profile["rain_high_action"] + " Avoid field work — storm conditions."

    # Pest/disease weather: moderate-heavy rain + warm = fungal risk
    if rain_mm > profile["rain_high_thresh"]:
        return "🟠 High Rain — Fungal Risk", "high", profile["rain_high_action"]

    # Heat stress
    if tmax > profile["heat_thresh"]:
        return "🟠 Heat Stress", "medium", profile["heat_action"]

    # Drought: almost no rain + hot
    if rain_mm < 1.5 and tmax > 28:
        return "🟡 Drought Risk", "medium", profile["drought_action"]

    # Foggy / cloudy — moderate notice
    if wmo_code in (45, 48):
        return "🟡 Fog / Low Visibility", "low", f"Foggy morning may slow {crop} drying. Delay sun-drying activities until mid-morning."

    return "🟢 Favorable", "low", profile["good_action"]


def get_weather_insights(region: str, crop: str):
    """
    Fetch 7-day Open-Meteo forecast and produce per-day risk + crop-specific advice.
    Returns (DataFrame, error_string_or_None).
    """
    lat, lon = MARKET_COORDS.get(region, (0.3476, 32.5825))  # default Kampala

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=Africa%2FKampala"
        f"&forecast_days=7"
    )

    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        daily = data["daily"]
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach Open-Meteo — check internet connection."
    except Exception as exc:
        return None, f"Weather API error: {exc}"

    rows = []
    for i in range(len(daily["time"])):
        date      = daily["time"][i]
        tmax      = daily["temperature_2m_max"][i] or 0.0
        tmin      = daily["temperature_2m_min"][i] or 0.0
        rain      = daily["precipitation_sum"][i] or 0.0
        wmo       = daily["weathercode"][i] or 0
        condition = WMO_DESCRIPTIONS.get(wmo, f"Code {wmo}")

        risk_label, risk_level, advice = classify_weather(rain, tmax, tmin, wmo, crop)

        rows.append({
            "Date":        date,
            "Condition":   condition,
            "Tmax (°C)":   tmax,
            "Tmin (°C)":   tmin,
            "Rain (mm)":   rain,
            "Risk":        risk_label,
            "_risk_level": risk_level,   # internal — for row colouring
            "Advice":      advice,
        })

    return pd.DataFrame(rows), None


def weather_row_style(row):
    """Row-level background colouring for the advice table."""
    level = row["_risk_level"]
    color = {
        "high":   "background-color: #3d000088",
        "medium": "background-color: #2d1a0088",
        "low":    "background-color: #002d1a44",
    }.get(level, "")
    return [color] * len(row)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.image(
    "https://img.shields.io/badge/AgriGuard-MVP-00cc66?style=for-the-badge&logo=leaf&logoColor=white",
    use_column_width=True,
)
st.sidebar.markdown("---")

base_url = st.sidebar.text_input(
    "🔌 Backend URL",
    value=DEFAULT_BASE,
    help="Change if your FastAPI server runs on a different port or host.",
)

# Health-check badge
health_data, health_err = api("GET", "/health", base_url)
if health_data:
    st.sidebar.markdown(
        f'<span class="status-dot-ok"></span> **Backend online** — v{health_data.get("version","?")}',
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        f'<span class="status-dot-err"></span> **Backend offline** — {health_err}',
        unsafe_allow_html=True,
    )

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Forecast Settings")

# Dynamic crop/market lists from backend
commodities_data, _ = api("GET", "/forecasts/commodities", base_url)
if commodities_data:
    available_crops   = commodities_data.get("commodities", [])
    available_markets = commodities_data.get("markets", [])
    obs_count         = commodities_data.get("total_observations", 0)
    st.sidebar.caption(f"📦 {obs_count:,} price observations loaded")
else:
    available_crops   = ["Maize", "Beans", "Cassava", "Coffee", "Matooke"]
    available_markets = list(MARKET_COORDS.keys())

crop    = st.sidebar.selectbox("🌽 Crop",   available_crops)
market  = st.sidebar.selectbox("📍 Market", available_markets)
horizon = st.sidebar.slider("📅 Forecast Horizon (days)", 7, 90, 14, step=7)

st.sidebar.markdown("---")
st.sidebar.caption("AgriGuard • Built by Keith Ndiema Kissa\nMUST 2025 • Ministry of ICT Showcase")

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("""
<h1 style='color:#00cc66; margin-bottom:0;'>🌾 AgriGuard</h1>
<p style='color:#888; margin-top:4px; font-size:1.05rem;'>
  Agricultural Intelligence Dashboard · Uganda
</p>
""", unsafe_allow_html=True)

if not health_data:
    st.warning(
        "⚠️ **Backend offline** — showing cached/demo data where possible. "
        "Start the FastAPI server with `uvicorn backend.app.main:app --reload`"
    )

st.divider()

# ─────────────────────────────────────────────
# TOP KPI ROW — National Summary
# ─────────────────────────────────────────────
ns_data, ns_err = api("GET", "/markets/national-summary", base_url)

if ns_data and ns_data.get("commodities"):
    comms   = ns_data["commodities"]
    rising  = sum(1 for c in comms if c["trend"] == "rising")
    falling = sum(1 for c in comms if c["trend"] == "falling")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-lbl">Commodities Tracked</div>
          <div class="metric-val">{len(comms)}</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        chosen = next((c for c in comms if c["commodity"].lower() == crop.lower()), None)
        val    = ugx(chosen["national_avg_price"]) if chosen else "—"
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-lbl">{crop} National Avg</div>
          <div class="metric-val">{val}</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-lbl">Rising Commodities</div>
          <div class="metric-val" style="color:#00cc66;">↑ {rising}</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-lbl">Falling Commodities</div>
          <div class="metric-val" style="color:#ff4c4c;">↓ {falling}</div>
        </div>""", unsafe_allow_html=True)
else:
    st.info("📊 National summary unavailable — connect backend to see live KPIs.")

st.divider()

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🌽 Price Forecast",
    "🔍 Input Validator",
    "📊 Market Intelligence",
    "🗺️ National Overview",
    "🌦️ Weather Insights",
])

# ══════════════════════════════════════════════
# TAB 1 — PRICE FORECAST
# ══════════════════════════════════════════════
with tab1:
    st.subheader(f"Price Forecast: **{crop}** in **{market}**")

    col_btn, col_info = st.columns([1, 3])
    run_forecast = col_btn.button("🚀 Generate Forecast", type="primary", use_container_width=True)
    col_info.caption(
        f"Calls `GET /forecasts/{crop}?market={market}&horizon={horizon}` → "
        "Prophet + optional XGBoost residual correction."
    )

    if run_forecast:
        with st.spinner(f"Running {horizon}-day forecast via backend ML pipeline…"):
            fc_data, fc_err = api(
                "GET",
                f"/forecasts/{crop}?market={market}&horizon={horizon}",
                base_url,
            )

        if fc_err:
            st.error(f"❌ Forecast failed: {fc_err}")
        else:
            m1, m2, m3, m4 = st.columns(4)
            pts    = fc_data["forecast"]
            prices = [p["predicted_price"] for p in pts]
            m1.metric("Model",     fc_data.get("model_used", "—"))
            m2.metric("Trend",     fc_data.get("trend", "—").title())
            m3.metric("% Change",  f"{fc_data.get('pct_change', 0):+.1f}%")
            m4.metric("Obs. used", f"{fc_data.get('observations_used', 0):,}")

            alert = fc_data.get("alert")
            if alert:
                level = "alert-high" if "📉" in alert else "alert-med"
                st.markdown(f'<div class="{level}">{alert}</div>', unsafe_allow_html=True)
                st.markdown("")

            # Forecast chart
            dates = [p["date"]        for p in pts]
            lower = [p["lower_bound"] for p in pts]
            upper = [p["upper_bound"] for p in pts]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates + dates[::-1],
                y=upper + lower[::-1],
                fill="toself",
                fillcolor="rgba(0,204,102,0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                name="90% Confidence Band",
                hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=dates, y=lower, mode="lines",
                line=dict(dash="dot", color="#f0a500", width=1),
                name="Lower Bound",
            ))
            fig.add_trace(go.Scatter(
                x=dates, y=upper, mode="lines",
                line=dict(dash="dot", color="#ff7c7c", width=1),
                name="Upper Bound",
            ))
            fig.add_trace(go.Scatter(
                x=dates, y=prices, mode="lines+markers",
                line=dict(color="#00cc66", width=3),
                marker=dict(size=6),
                name="Predicted Price",
                hovertemplate="<b>%{x}</b><br>Price: UGX %{y:,.0f}<extra></extra>",
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                hovermode="x unified",
                legend=dict(orientation="h", y=-0.2),
                xaxis_title="Date",
                yaxis_title=f"Price (UGX / {fc_data.get('unit','kg')})",
                margin=dict(l=10, r=10, t=10, b=10),
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📈 View Historical Price Context (last 12 months)"):
                hist_data, hist_err = api(
                    "GET",
                    f"/forecasts/history/{crop}?market={market}&days=365",
                    base_url,
                )
                if hist_data and hist_data.get("history"):
                    hdf  = pd.DataFrame(hist_data["history"])
                    hfig = go.Figure()
                    hfig.add_trace(go.Scatter(
                        x=hdf["date"], y=hdf["price"],
                        mode="lines", line=dict(color="#888", width=1.5),
                        name="Historical",
                    ))
                    hfig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=220,
                        margin=dict(l=10, r=10, t=10, b=10),
                        showlegend=False,
                    )
                    st.plotly_chart(hfig, use_container_width=True)
                else:
                    st.info(hist_err or "No historical data available.")

            with st.expander("📋 Raw Forecast Data"):
                df_fc = pd.DataFrame(pts)
                df_fc["predicted_price"] = df_fc["predicted_price"].apply(lambda x: f"UGX {x:,.0f}")
                df_fc["lower_bound"]     = df_fc["lower_bound"].apply(lambda x: f"UGX {x:,.0f}")
                df_fc["upper_bound"]     = df_fc["upper_bound"].apply(lambda x: f"UGX {x:,.0f}")
                df_fc["confidence"]      = df_fc["confidence"].apply(lambda x: f"{x*100:.0f}%")
                st.dataframe(df_fc, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Quick Price Signal  *(from ML predict endpoint)*")
    pred_col1, pred_col2 = st.columns([2, 1])
    with pred_col1:
        pred_date = st.date_input("Prediction date", value=datetime.today() + timedelta(days=7))
    run_pred = pred_col2.button("⚡ Quick Predict", use_container_width=True)

    if run_pred:
        payload = {"crop": crop.lower(), "region": market, "date": str(pred_date)}
        pred_data, pred_err = api("POST", "/api/v1/predict", base_url, json=payload)
        if pred_err:
            st.error(f"Predict error: {pred_err}")
        else:
            pa, pb, pc, pd_ = st.columns(4)
            pa.metric("Predicted Price",  ugx(pred_data.get("predicted_price")))
            pb.metric("Trend",            pred_data.get("trend", "—").title())
            pc.metric("Recommendation",   pred_data.get("recommendation", "—"))
            pd_.metric("Confidence",      f"{pred_data.get('confidence', 0)*100:.0f}%")

# ══════════════════════════════════════════════
# TAB 2 — FAKE INPUT DETECTOR
# ══════════════════════════════════════════════
with tab2:
    st.subheader("🔍 Agricultural Input Validator")
    st.caption("Calls `POST /api/v1/validate` — checks crop, region and date for anomalies.")

    with st.form("validator_form"):
        vc1, vc2, vc3 = st.columns(3)
        v_crop   = vc1.selectbox("🌽 Crop",   available_crops, key="v_crop")
        v_region = vc2.text_input("📍 Region", value=market,    key="v_region")
        v_date   = vc3.date_input("📅 Date",   value=datetime.today(), key="v_date")
        submitted = st.form_submit_button("🔎 Validate Input", type="primary", use_container_width=True)

    if submitted:
        payload = {"crop": v_crop.lower(), "region": v_region, "date": str(v_date)}
        with st.spinner("Running validation pipeline…"):
            val_data, val_err = api("POST", "/api/v1/validate", base_url, json=payload)

        if val_err:
            st.error(f"Validation call failed: {val_err}")
        else:
            is_valid = val_data.get("is_valid", False)
            is_fake  = val_data.get("is_fake",  False)
            conf     = val_data.get("confidence", 0)
            errors   = val_data.get("errors") or []
            reason   = val_data.get("reason", "")

            if is_valid:
                st.success(f"✅ **INPUT VALID** — Confidence: **{conf*100:.0f}%**")
                st.balloons()
            else:
                st.error(f"⚠️ **SUSPICIOUS / INVALID INPUT** — Confidence: **{conf*100:.0f}%**")

            r1, r2, r3 = st.columns(3)
            r1.metric("Valid?",     "✅ Yes" if is_valid else "❌ No")
            r2.metric("Flagged?",   "🚩 Yes" if is_fake  else "✅ No")
            r3.metric("Confidence", f"{conf*100:.0f}%")

            if reason:
                st.info(f"**Reason:** {reason}")
            if errors:
                st.warning("**Validation errors:**\n" + "\n".join(f"- {e}" for e in errors))

    st.markdown("---")
    st.markdown("#### Batch Validation")
    st.caption("Upload a CSV with columns `crop, region, date` to validate multiple records at once.")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        try:
            df_batch = pd.read_csv(uploaded)
            required = {"crop", "region", "date"}
            if not required.issubset(df_batch.columns):
                st.error(f"CSV must have columns: {required}")
            else:
                results = []
                bar = st.progress(0)
                for i, row in df_batch.iterrows():
                    payload = {
                        "crop":   str(row["crop"]).lower(),
                        "region": str(row["region"]),
                        "date":   str(row["date"]),
                    }
                    res, _ = api("POST", "/api/v1/validate", base_url, json=payload)
                    if res:
                        results.append({
                            **row.to_dict(),
                            "valid":      res.get("is_valid"),
                            "flagged":    res.get("is_fake"),
                            "confidence": f"{res.get('confidence',0)*100:.0f}%",
                        })
                    bar.progress((i + 1) / len(df_batch))
                st.dataframe(pd.DataFrame(results), use_container_width=True)
        except Exception as exc:
            st.error(f"Error processing CSV: {exc}")

# ══════════════════════════════════════════════
# TAB 3 — MARKET INTELLIGENCE
# ══════════════════════════════════════════════
with tab3:
    st.subheader("📊 Market Intelligence")

    mi_c1, mi_c2 = st.columns(2)

    # Price Movers
    with mi_c1:
        st.markdown("#### 🔥 Top Price Movers (last 30 days)")
        movers_data, movers_err = api("GET", "/markets/movers?period_days=30&top_n=5", base_url)
        if movers_err:
            st.error(movers_err)
        elif movers_data:
            gainers = movers_data.get("gainers", [])
            losers  = movers_data.get("losers",  [])
            for g in gainers:
                level = g.get("alert_level", "low")
                css   = "alert-high" if level == "high" else "alert-med" if level == "medium" else "alert-low"
                st.markdown(
                    f'<div class="{css}">📈 <b>{g["commodity"]}</b> in {g["market"]} '
                    f'→ +{g["change_pct"]:.1f}% ({ugx(g["latest_price"])})</div>',
                    unsafe_allow_html=True,
                )
            st.markdown("")
            for l in losers:
                st.markdown(
                    f'<div class="alert-high">📉 <b>{l["commodity"]}</b> in {l["market"]} '
                    f'→ {l["change_pct"]:.1f}% ({ugx(l["latest_price"])})</div>',
                    unsafe_allow_html=True,
                )

    # Cross-market comparison
    with mi_c2:
        st.markdown(f"#### 🗺️ {crop} — Cross-Market Prices")
        summary_data, summary_err = api("GET", f"/markets/summary/{crop}", base_url)
        if summary_err:
            st.error(summary_err)
        elif summary_data:
            mkts = summary_data.get("markets", [])
            if mkts:
                df_mkts = pd.DataFrame([{
                    "Market":       m["market"],
                    "Price (UGX)":  m["latest_price"],
                    "30d Chg %":    m.get("price_change_pct") or 0,
                    "Trend":        m.get("trend", "stable").title(),
                } for m in mkts])

                fig_bar = px.bar(
                    df_mkts, x="Market", y="Price (UGX)",
                    color="30d Chg %",
                    color_continuous_scale=["#ff4c4c", "#f0a500", "#00cc66"],
                    template="plotly_dark",
                    title=f"{crop} prices across markets",
                )
                fig_bar.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=340,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                best  = df_mkts.loc[df_mkts["Price (UGX)"].idxmax()]
                worst = df_mkts.loc[df_mkts["Price (UGX)"].idxmin()]
                mc1, mc2 = st.columns(2)
                mc1.metric("Best market to sell", best["Market"],
                           delta=f"UGX {best['Price (UGX)']:,.0f}")
                mc2.metric("Cheapest to buy", worst["Market"],
                           delta=f"UGX {worst['Price (UGX)']:,.0f}")

# ══════════════════════════════════════════════
# TAB 4 — NATIONAL OVERVIEW
# ══════════════════════════════════════════════
with tab4:
    st.subheader("🗺️ National Overview")

    if ns_data and ns_data.get("commodities"):
        comms = ns_data["commodities"]
        df_ns = pd.DataFrame([{
            "Commodity":      c["commodity"],
            "National Avg":   ugx(c["national_avg_price"]),
            "Markets":        c.get("market_count", "—"),
            "Trend":          c.get("trend", "stable").title(),
            "Highest Price":  ugx(c.get("highest_price")),
            "Lowest Price":   ugx(c.get("lowest_price")),
        } for c in comms])
        st.dataframe(df_ns, use_container_width=True, hide_index=True)

        # Radar / scatter of price spread
        if len(comms) >= 2:
            spread_data = [{
                "Commodity": c["commodity"],
                "Spread":    (c.get("highest_price") or 0) - (c.get("lowest_price") or 0),
                "Avg":       c["national_avg_price"],
            } for c in comms]
            df_spread = pd.DataFrame(spread_data)
            fig_sp = px.scatter(
                df_spread, x="Avg", y="Spread",
                text="Commodity",
                template="plotly_dark",
                labels={"Avg": "National Avg Price (UGX)", "Spread": "Market Price Spread (UGX)"},
                title="Price Spread vs. National Average — spot arbitrage opportunities",
            )
            fig_sp.update_traces(
                marker=dict(size=14, color="#00cc66", line=dict(width=2, color="#ffffff")),
                textposition="top center",
            )
            fig_sp.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=380,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_sp, use_container_width=True)
            st.caption(
                "Commodities with a **large spread** and **high average** offer the best arbitrage opportunity — "
                "buy in the cheapest market, sell in the most expensive."
            )
    else:
        st.info("📊 National summary unavailable — start the backend to see this view.")

# ══════════════════════════════════════════════
# TAB 5 — WEATHER INSIGHTS
# ══════════════════════════════════════════════
with tab5:
    st.subheader(f"🌦️ Weather Insights: **{crop}** in **{market}**")
    st.caption(
        "Live 7-day forecast from Open-Meteo (free, no key needed) "
        "with crop-specific risk classification and actionable farmer advice."
    )

    # Auto-load on tab open; re-fetch button for manual refresh
    if "weather_df" not in st.session_state or st.session_state.get("weather_key") != f"{crop}_{market}":
        with st.spinner("Fetching weather data from Open-Meteo…"):
            _df, _err = get_weather_insights(market, crop)
        st.session_state["weather_df"]  = _df
        st.session_state["weather_err"] = _err
        st.session_state["weather_key"] = f"{crop}_{market}"

    if st.button("🔄 Refresh Weather Data"):
        with st.spinner("Refreshing…"):
            _df, _err = get_weather_insights(market, crop)
        st.session_state["weather_df"]  = _df
        st.session_state["weather_err"] = _err

    weather_df  = st.session_state["weather_df"]
    weather_err = st.session_state["weather_err"]

    if weather_err:
        st.error(f"❌ {weather_err}")
        st.stop()

    if weather_df is None or weather_df.empty:
        st.warning("No weather data returned. Try refreshing.")
        st.stop()

    # ── KPI strip
    avg_rain        = weather_df["Rain (mm)"].mean()
    max_t           = weather_df["Tmax (°C)"].max()
    high_risk_days  = (weather_df["_risk_level"] == "high").sum()
    med_risk_days   = (weather_df["_risk_level"] == "medium").sum()
    good_days       = (weather_df["_risk_level"] == "low").sum()

    w1, w2, w3, w4, w5 = st.columns(5)
    w1.metric("📍 Region", market)
    w2.metric("🌧️ Avg Rainfall",    f"{avg_rain:.1f} mm/day")
    w3.metric("🌡️ Peak Temp",       f"{max_t:.1f} °C")
    w4.metric("🔴 High-Risk Days",  int(high_risk_days))
    w5.metric("🟢 Favorable Days",  int(good_days))

    # ── Alert banner if any high-risk days
    if high_risk_days > 0:
        high_rows = weather_df[weather_df["_risk_level"] == "high"]
        alerts = " · ".join(
            f"{r['Date']} ({r['Risk']})" for _, r in high_rows.iterrows()
        )
        st.markdown(
            f'<div class="alert-high">⚠️ <b>High-risk weather detected:</b> {alerts}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")

    # ── Dual-axis chart: rainfall bars + temperature line
    fig_w = go.Figure()

    fig_w.add_trace(go.Bar(
        x=weather_df["Date"],
        y=weather_df["Rain (mm)"],
        name="Rainfall (mm)",
        marker_color="#1E90FF",
        opacity=0.75,
        yaxis="y",
    ))
    fig_w.add_trace(go.Scatter(
        x=weather_df["Date"],
        y=weather_df["Tmax (°C)"],
        name="Tmax (°C)",
        mode="lines+markers",
        line=dict(color="#FF4500", width=2.5),
        marker=dict(size=7),
        yaxis="y2",
    ))
    fig_w.add_trace(go.Scatter(
        x=weather_df["Date"],
        y=weather_df["Tmin (°C)"],
        name="Tmin (°C)",
        mode="lines",
        line=dict(color="#FFA07A", width=1.5, dash="dot"),
        yaxis="y2",
    ))

    # Highlight high-risk days as background shading
    for _, row in weather_df[weather_df["_risk_level"] == "high"].iterrows():
        fig_w.add_vrect(
            x0=row["Date"], x1=row["Date"],
            fillcolor="rgba(255,76,76,0.15)",
            layer="below", line_width=0,
        )

    fig_w.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=400,
        title=f"7-Day Weather Forecast — {market}",
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.2),
        yaxis  =dict(title="Rainfall (mm)", side="left"),
        yaxis2 =dict(title="Temperature (°C)", side="right", overlaying="y"),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig_w, use_container_width=True)

    # ── Daily advice cards
    st.markdown("### 📋 Daily Crop Advice")
    for _, row in weather_df.iterrows():
        level = row["_risk_level"]
        card_border = {"high": "#ff4c4c", "medium": "#f0a500", "low": "#00cc66"}.get(level, "#00cc66")
        risk_class  = {"high": "weather-risk-high", "medium": "weather-risk-med", "low": "weather-risk-low"}.get(level, "weather-risk-low")

        st.markdown(f"""
        <div class="weather-card" style="border-color:{card_border}55;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <b style="color:#ddd;">{row['Date']}</b>
            <span class="{risk_class}">{row['Risk']}</span>
          </div>
          <div style="color:#aaa; font-size:0.82rem; margin:3px 0;">
            {row['Condition']} &nbsp;|&nbsp; 🌡️ {row['Tmin (°C)']}–{row['Tmax (°C)']}°C &nbsp;|&nbsp;
            🌧️ {row['Rain (mm)']} mm
          </div>
          <div class="weather-advice">💡 {row['Advice']}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Cross-link tip
    if high_risk_days > 0 or med_risk_days > 0:
        st.info(
            "💡 **Price impact tip:** High rain or heat events often cause supply disruptions "
            "— check the **Price Forecast** tab to see if this aligns with an upward price signal for "
            f"{crop} in {market}."
        )

    # ── Raw data expander
    with st.expander("📋 Raw Weather Data"):
        st.dataframe(
            weather_df.drop(columns=["_risk_level"]).style.apply(weather_row_style, axis=1),
            use_container_width=True,
            hide_index=True,
        )

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.divider()
st.caption(
    "AgriGuard · Agricultural Intelligence for Uganda · "
    "Built by Keith Ndiema Kissa · MUST 2026 · Ministry of ICT Showcase · "
    "Data: Open-Meteo (weather), AgriGuard FastAPI backend (prices)"
)