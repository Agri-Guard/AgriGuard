import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import os

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AgriGuard",
    page_icon="🌾",
    layout="wide",
)

st.title("🌾 AgriGuard — Agricultural Intelligence Dashboard")
st.caption("Crop price forecasting for Uganda markets")


@st.cache_data(ttl=300)
def fetch_commodities():
    try:
        r = requests.get(f"{API_URL}/predictions/commodities", timeout=5)
        return r.json()
    except Exception:
        return ["Maize", "Beans", "Sorghum", "Cassava"]


@st.cache_data(ttl=300)
def fetch_markets():
    try:
        r = requests.get(f"{API_URL}/predictions/markets", timeout=5)
        return r.json()
    except Exception:
        return ["Kampala", "Mbarara", "Gulu", "Mbale", "Jinja"]


@st.cache_data(ttl=60)
def fetch_forecast(commodity: str, market: str, weeks: int):
    r = requests.get(
        f"{API_URL}/predictions/forecast",
        params={"commodity": commodity, "market": market, "weeks": weeks},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# Sidebar controls
with st.sidebar:
    st.header("Settings")
    commodities = fetch_commodities()
    markets = fetch_markets()

    selected_commodity = st.selectbox("Crop", commodities)
    selected_market = st.selectbox("Market", markets)
    forecast_weeks = st.slider("Forecast Weeks", min_value=1, max_value=24, value=8)
    run = st.button("Get Forecast", type="primary")

# Main content
if run:
    with st.spinner(f"Forecasting {selected_commodity} prices in {selected_market}..."):
        try:
            data = fetch_forecast(selected_commodity, selected_market, forecast_weeks)
            df = pd.DataFrame(data["forecasts"])
            df["date"] = pd.to_datetime(df["date"])

            col1, col2, col3 = st.columns(3)
            col1.metric("Next Week", f"UGX {df.iloc[0]['price_ugx']:,.0f}")
            col2.metric(
                f"Week {forecast_weeks}",
                f"UGX {df.iloc[-1]['price_ugx']:,.0f}",
                delta=f"{df.iloc[-1]['price_ugx'] - df.iloc[0]['price_ugx']:+,.0f}",
            )
            col3.metric("Market", selected_market)

            # Forecast chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["upper_ugx"],
                fill=None, mode="lines",
                line=dict(color="rgba(0,100,0,0.1)"),
                name="Upper bound",
            ))
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["lower_ugx"],
                fill="tonexty", mode="lines",
                line=dict(color="rgba(0,100,0,0.1)"),
                fillcolor="rgba(0,150,0,0.15)",
                name="Lower bound",
            ))
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["price_ugx"],
                mode="lines+markers",
                line=dict(color="#2e7d32", width=2),
                marker=dict(size=6),
                name="Forecast price",
            ))
            fig.update_layout(
                title=f"{selected_commodity} Price Forecast — {selected_market}",
                xaxis_title="Date",
                yaxis_title="Price (UGX/kg)",
                hovermode="x unified",
                legend=dict(orientation="h", y=-0.2),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Raw table
            with st.expander("View forecast data"):
                st.dataframe(
                    df.rename(columns={
                        "date": "Date",
                        "price_ugx": "Price (UGX/kg)",
                        "lower_ugx": "Lower Bound",
                        "upper_ugx": "Upper Bound",
                    }).set_index("Date"),
                    use_container_width=True,
                )

        except requests.HTTPError as e:
            st.error(f"API error: {e.response.json().get('detail', str(e))}")
        except Exception as e:
            st.error(f"Could not connect to API: {e}. Is the backend running?")
else:
    st.info("Select a crop and market in the sidebar, then click **Get Forecast**.")

st.divider()
st.caption("AgriGuard · Built by Keith Ndiema Kissa · Mbarara University of Science and Technology")