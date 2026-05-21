import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import os

# =====================
# CONFIG
# =====================
API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AgriGuard",
    page_icon="🌾",
    layout="wide",
)

# =====================
# API HELPER (ROBUST)
# =====================
def safe_get(url, params=None, fallback=None):
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return fallback


# =====================
# HEADER
# =====================
st.title("🌾 AgriGuard — Agricultural Intelligence Dashboard")
st.caption("AI-powered crop price forecasting for Uganda agricultural markets")

# =====================
# API STATUS INDICATOR
# =====================
status = safe_get(f"{API_URL}/health", fallback=None)

if status:
    st.success("🟢 Backend Connected")
else:
    st.error("🔴 Backend Not Available — running in offline mode")

st.divider()


# =====================
# DATA LOADERS
# =====================
@st.cache_data(ttl=300)
def fetch_commodities():
    return safe_get(f"{API_URL}/predictions/commodities",
                    fallback=["Maize", "Beans", "Sorghum", "Cassava"])


@st.cache_data(ttl=300)
def fetch_markets():
    return safe_get(f"{API_URL}/predictions/markets",
                    fallback=["Kampala", "Mbarara", "Gulu", "Mbale", "Jinja"])


@st.cache_data(ttl=60)
def fetch_forecast(commodity, market, weeks):
    return safe_get(
        f"{API_URL}/predictions/forecast",
        params={"commodity": commodity, "market": market, "weeks": weeks},
        fallback=None
    )


# =====================
# SIDEBAR
# =====================
with st.sidebar:
    st.header("⚙️ Forecast Settings")

    commodities = fetch_commodities()
    markets = fetch_markets()

    selected_commodity = st.selectbox("🌱 Crop", commodities)
    selected_market = st.selectbox("🏪 Market", markets)
    forecast_weeks = st.slider("📅 Forecast Horizon (Weeks)", 1, 24, 8)

    st.divider()
    run = st.button("🚀 Generate Forecast", type="primary")


# =====================
# MAIN LOGIC
# =====================
if run:

    with st.spinner("AI models analyzing market trends..."):
        data = fetch_forecast(selected_commodity, selected_market, forecast_weeks)

    if not data:
        st.error("No forecast data returned from API.")
        st.stop()

    df = pd.DataFrame(data["forecasts"])
    df["date"] = pd.to_datetime(df["date"])

    # =====================
    # INSIGHTS ENGINE (MVP intelligence layer)
    # =====================
    start_price = df.iloc[0]["price_ugx"]
    end_price = df.iloc[-1]["price_ugx"]
    change = end_price - start_price
    pct_change = (change / start_price) * 100

    trend = "📈 Rising Market" if change > 0 else "📉 Falling Market"

    # =====================
    # METRICS
    # =====================
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Next Week Price", f"UGX {start_price:,.0f}")
    col2.metric(
        f"{forecast_weeks}-Week Outlook",
        f"UGX {end_price:,.0f}",
        delta=f"{change:+,.0f} ({pct_change:+.2f}%)"
    )
    col3.metric("Market", selected_market)
    col4.metric("Trend", trend)

    st.divider()

    # =====================
    # INSIGHT BOX
    # =====================
    st.info(
        f"""
        💡 **Market Insight**

        {selected_commodity} prices in {selected_market} show a **{trend.lower()}** over the forecast period.

        - Expected change: **{pct_change:+.2f}%**
        - Suggestion: {"Consider selling early 📦" if change > 0 else "Good time to hold stock 🏦"}
        """
    )

    # =====================
    # CHART
    # =====================
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["upper_ugx"],
        fill=None, mode="lines",
        line=dict(color="rgba(0,100,0,0.1)"),
        name="Upper Bound",
    ))

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["lower_ugx"],
        fill="tonexty", mode="lines",
        line=dict(color="rgba(0,100,0,0.1)"),
        fillcolor="rgba(0,150,0,0.15)",
        name="Lower Bound",
    ))

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["price_ugx"],
        mode="lines+markers",
        line=dict(width=3),
        marker=dict(size=6),
        name="Forecast Price",
    ))

    fig.update_layout(
        title=f"{selected_commodity} Price Forecast — {selected_market}",
        xaxis_title="Date",
        yaxis_title="Price (UGX/kg)",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", y=-0.2),
    )

    st.plotly_chart(fig, use_container_width=True)

    # =====================
    # DATA TABLE
    # =====================
    with st.expander("📊 View Raw Forecast Data"):
        st.dataframe(
            df.rename(columns={
                "date": "Date",
                "price_ugx": "Price (UGX/kg)",
                "lower_ugx": "Lower Bound",
                "upper_ugx": "Upper Bound",
            }),
            use_container_width=True
        )

else:
    st.info("👈 Select a crop and market, then click **Generate Forecast** to begin analysis.")

# =====================
# FOOTER
# =====================
st.divider()
st.caption("AgriGuard · Smart Agricultural Intelligence System · Built by Keith Ndiema Kissa · MUST")