import streamlit as st

st.set_page_config(page_title="AgriGuard", page_icon="🌾", layout="wide")

# ===================== HERO SECTION =====================
st.markdown("""
    <h1 style='text-align: center; color: #00cc66;'>
        🌾 AgriGuard
    </h1>
""", unsafe_allow_html=True)

st.markdown("""
    <h3 style='text-align: center;'>
        Agricultural Intelligence System for Uganda
    </h3>
""", unsafe_allow_html=True)

st.caption("""
    <p style='text-align: center;'>
        Improving food security through AI-powered price forecasting & counterfeit detection
    </p>
""", unsafe_allow_html=True)

st.divider()

# Features Overview
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🌽 Price Forecasting")
    st.write("Predict future prices of major crops across Ugandan markets.")
    st.button("Open Forecasting Tool →", key="btn_forecast", use_container_width=True)

with col2:
    st.markdown("### 🔍 Fake Input Detector")
    st.write("Verify authenticity of seeds, fertilizers & agro inputs.")
    st.button("Check Product Authenticity →", key="btn_detector", use_container_width=True)

with col3:
    st.markdown("### 📊 Market Insights")
    st.write("Real-time market trends and agribusiness intelligence.")
    st.button("View Market Data →", key="btn_insights", use_container_width=True)

st.divider()

# Call to Action
st.markdown("### Ready to explore?")
if st.button("🚀 Go to Full Dashboard", type="primary", use_container_width=True):
    st.switch_page("pages/dashboard.py")

# Quick Demo Section
st.subheader("Quick Demo")
st.info("""
    **Try it now:**
    - Select different crops and markets
    - Adjust forecast duration
    - Test the Fake Input Detector
""")

# Footer
st.divider()
st.caption("AgriGuard • Smart Agricultural Intelligence System • Built by Keith Ndiema Kissa • For Ministry of ICT & National Guidance Prototype Showcase")