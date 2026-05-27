import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="AgriGuard Dashboard", page_icon="🌾", layout="wide")

# ===================== SIDEBAR =====================
st.sidebar.title("🌾 AgriGuard")
st.sidebar.markdown("### Forecast Settings")

crop = st.sidebar.selectbox(
    "🌽 Select Crop",
    options=["Maize", "Matooke", "Coffee", "Beans", "Cassava"],
    key="crop"
)

market = st.sidebar.selectbox(
    "📍 Select Market",
    options=["Kampala", "Mbarara", "Gulu", "Mbale", "Jinja", "Lira"],
    key="market"
)

duration = st.sidebar.slider(
    "📅 Forecast Duration (Days)",
    min_value=7,
    max_value=30,
    value=14,
    step=7
)

st.sidebar.markdown("---")
st.sidebar.info("**Demo Mode** — Backend offline")

# ===================== MAIN CONTENT =====================
st.title("🌾 AgriGuard — Agricultural Intelligence Dashboard")
st.subheader("AI-powered crop price forecasting & market intelligence for Uganda")

st.warning("🔌 **Running in Offline/Demo Mode** — Backend not connected yet")

st.divider()

# Tabs inside Dashboard
tab1, tab2, tab3 = st.tabs(["🌽 Price Forecasting", "🔍 Fake Input Detector", "📊 Market Insights"])

# ===================== PRICE FORECASTING =====================
with tab1:
    st.subheader(f"Price Forecast: {crop} in {market}")
    
    if st.button("🚀 Generate Forecast", type="primary", use_container_width=True):
        with st.spinner(f"Generating {duration}-day forecast..."):
            dates = [(datetime.now() + timedelta(days=i)).strftime("%b %d") for i in range(duration)]
            
            base_prices = {"Maize": 1250, "Matooke": 2400, "Coffee": 8500, 
                         "Beans": 1800, "Cassava": 900}
            base = base_prices.get(crop, 1500)
            
            np.random.seed(42)
            prices = [base + np.random.randint(-180, 280) for _ in range(duration)]
            
            df = pd.DataFrame({
                "Date": dates,
                "Predicted Price (UGX/kg)": prices,
                "Lower Bound": [int(p * 0.92) for p in prices],
                "Upper Bound": [int(p * 1.08) for p in prices]
            })

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=prices, mode='lines+markers', 
                                   name='Predicted Price', line=dict(color='#00cc66', width=3)))
            fig.add_trace(go.Scatter(x=dates, y=[p*0.92 for p in prices], 
                                   mode='lines', name='Lower Bound', line=dict(dash='dash', color='orange')))
            fig.add_trace(go.Scatter(x=dates, y=[p*1.08 for p in prices], 
                                   mode='lines', name='Upper Bound', line=dict(dash='dash', color='red')))

            fig.update_layout(
                title=f"{duration}-Day Price Forecast — {crop} • {market}",
                xaxis_title="Date",
                yaxis_title="Price (UGX per Kg)",
                template="plotly_dark",
                hovermode="x unified",
                legend=dict(orientation="h", y=-0.2)
            )

            st.plotly_chart(fig, use_container_width=True)
            st.success(f"✅ {duration}-day forecast generated for **{crop}** in **{market}**")
            
            with st.expander("📋 View Forecast Data Table"):
                st.dataframe(df, use_container_width=True)

# ===================== FAKE INPUT DETECTOR =====================
with tab2:
    st.subheader("🔍 Fake Input / Counterfeit Detector")
    st.write("Verify authenticity of agricultural inputs")
    
    col1, col2 = st.columns(2)
    with col1:
        product = st.text_input("Product Name / Batch No", placeholder="e.g. Hybrid Maize Seed - Batch UG-2026-045")
    with col2:
        supplier = st.selectbox("Supplier", ["NAADS", "UNADA", "Local Agrovet", "Government Certified", "Other"])
    
    if st.button("🔎 Verify Product", type="primary", use_container_width=True):
        with st.spinner("Scanning & verifying..."):
            score = np.random.randint(72, 98)
            if score >= 85:
                st.success(f"✅ **GENUINE PRODUCT** — Confidence: **{score}%**")
                st.balloons()
            else:
                st.error(f"⚠️ **HIGH RISK OF COUNTERFEIT** — Confidence: **{score}%**")
            
            st.info("**Recommendation**: Purchase only from authorized NAADS distributors.")

# ===================== MARKET INSIGHTS =====================
with tab3:
    st.subheader("📊 Current Market Insights")
    
    if st.button("🔄 Refresh Market Data", type="primary"):
        st.success("Market data refreshed!")
    
    # Mock market data
    market_data = {
        "Crop": ["Maize", "Matooke", "Coffee", "Beans"],
        "Current Price (UGX/kg)": [1320, 2380, 8700, 1750],
        "7-Day Change": ["+6.5%", "-2.1%", "+11.3%", "+4.8%"],
        "Trend": ["Rising", "Stable", "Rising Strongly", "Rising"]
    }
    
    st.dataframe(pd.DataFrame(market_data), use_container_width=True, height=300)
    
    st.info("💡 **Insight**: Coffee prices expected to remain strong due to export demand.")

st.divider()
st.caption("AgriGuard • Smart Agricultural Intelligence System • Built by Keith Ndiema Kissa • For Ministry of ICT Prototype Showcase")