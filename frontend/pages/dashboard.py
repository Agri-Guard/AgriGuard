"""
AgriGuard Dashboard — Backend-Connected
=========================================
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
    .alert-high  { background:#3d0000; border-left:4px solid #ff4c4c; padding:8px 12px; border-radius:4px; }
    .alert-med   { background:#2d1a00; border-left:4px solid #f0a500; padding:8px 12px; border-radius:4px; }
    .alert-low   { background:#002d1a; border-left:4px solid #00cc66; padding:8px 12px; border-radius:4px; }
    .status-dot-ok  { display:inline-block; width:10px; height:10px; border-radius:50%; background:#00cc66; margin-right:6px; }
    .status-dot-err { display:inline-block; width:10px; height:10px; border-radius:50%; background:#ff4c4c; margin-right:6px; }
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
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.image(
    "https://img.shields.io/badge/AgriGuard-MVP-00cc66?style=for-the-badge&logo=leaf&logoColor=white",
    use_column_width=True
)
st.sidebar.markdown("---")

base_url = st.sidebar.text_input(
    "🔌 Backend URL",
    value=DEFAULT_BASE,
    help="Change if your FastAPI server runs on a different port or host."
)

# Health-check badge
health_data, health_err = api("GET", "/health", base_url)
if health_data:
    st.sidebar.markdown(
        f'<span class="status-dot-ok"></span> **Backend online** — v{health_data.get("version","?")}',
        unsafe_allow_html=True
    )
else:
    st.sidebar.markdown(
        f'<span class="status-dot-err"></span> **Backend offline** — {health_err}',
        unsafe_allow_html=True
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
    # Sensible fallbacks when backend is offline
    available_crops   = ["Maize", "Beans", "Cassava", "Coffee", "Matooke"]
    available_markets = ["Kampala", "Mbarara", "Gulu", "Mbale", "Jinja", "Lira"]

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
    st.warning("⚠️ **Backend offline** — showing cached/demo data where possible. Start the FastAPI server with `uvicorn backend.app.main:app --reload`")

st.divider()

# ─────────────────────────────────────────────
# TOP KPI ROW — National Summary
# ─────────────────────────────────────────────
ns_data, ns_err = api("GET", "/markets/national-summary", base_url)

if ns_data and ns_data.get("commodities"):
    comms = ns_data["commodities"]
    # 4 headline metrics
    avg_prices = [c["national_avg_price"] for c in comms]
    rising     = sum(1 for c in comms if c["trend"] == "rising")
    falling    = sum(1 for c in comms if c["trend"] == "falling")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-lbl">Commodities Tracked</div>
          <div class="metric-val">{len(comms)}</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        # Find chosen crop in national summary
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
tab1, tab2, tab3, tab4 = st.tabs([
    "🌽 Price Forecast",
    "🔍 Input Validator",
    "📊 Market Intelligence",
    "🗺️ National Overview",
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
                base_url
            )

        if fc_err:
            st.error(f"❌ Forecast failed: {fc_err}")
        else:
            # ── Prediction quick stats
            m1, m2, m3, m4 = st.columns(4)
            pts = fc_data["forecast"]
            prices = [p["predicted_price"] for p in pts]
            m1.metric("Model", fc_data.get("model_used", "—"))
            m2.metric("Trend", fc_data.get("trend", "—").title())
            m3.metric("% Change", f"{fc_data.get('pct_change', 0):+.1f}%")
            m4.metric("Obs. used", f"{fc_data.get('observations_used', 0):,}")

            alert = fc_data.get("alert")
            if alert:
                level = "alert-high" if "📉" in alert else "alert-med"
                st.markdown(f'<div class="{level}">{alert}</div>', unsafe_allow_html=True)
                st.markdown("")

            # ── Forecast chart
            dates  = [p["date"] for p in pts]
            lower  = [p["lower_bound"] for p in pts]
            upper  = [p["upper_bound"] for p in pts]
            conf   = [round(p["confidence"] * 100) for p in pts]

            fig = go.Figure()
            # Confidence band
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
                name="Lower Bound"
            ))
            fig.add_trace(go.Scatter(
                x=dates, y=upper, mode="lines",
                line=dict(dash="dot", color="#ff7c7c", width=1),
                name="Upper Bound"
            ))
            fig.add_trace(go.Scatter(
                x=dates, y=prices, mode="lines+markers",
                line=dict(color="#00cc66", width=3),
                marker=dict(size=6),
                name="Predicted Price",
                hovertemplate="<b>%{x}</b><br>Price: UGX %{y:,.0f}<extra></extra>"
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

            # ── Also fetch historical context
            with st.expander("📈 View Historical Price Context (last 12 months)"):
                hist_data, hist_err = api(
                    "GET",
                    f"/forecasts/history/{crop}?market={market}&days=365",
                    base_url
                )
                if hist_data and hist_data.get("history"):
                    hpts = hist_data["history"]
                    hdf  = pd.DataFrame(hpts)
                    hfig = go.Figure()
                    hfig.add_trace(go.Scatter(
                        x=hdf["date"], y=hdf["price"],
                        mode="lines", line=dict(color="#888", width=1.5),
                        name="Historical"
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

            # ── Raw table
            with st.expander("📋 Raw Forecast Data"):
                df_fc = pd.DataFrame(pts)
                df_fc["predicted_price"] = df_fc["predicted_price"].apply(lambda x: f"UGX {x:,.0f}")
                df_fc["lower_bound"]     = df_fc["lower_bound"].apply(lambda x: f"UGX {x:,.0f}")
                df_fc["upper_bound"]     = df_fc["upper_bound"].apply(lambda x: f"UGX {x:,.0f}")
                df_fc["confidence"]      = df_fc["confidence"].apply(lambda x: f"{x*100:.0f}%")
                st.dataframe(df_fc, use_container_width=True)

    # Also show the quick MVP predict endpoint result
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
            pa.metric("Predicted Price", ugx(pred_data.get("predicted_price")))
            pb.metric("Trend", pred_data.get("trend", "—").title())
            pc.metric("Recommendation", pred_data.get("recommendation", "—"))
            pd_.metric("Confidence", f"{pred_data.get('confidence', 0)*100:.0f}%")


# ══════════════════════════════════════════════
# TAB 2 — FAKE INPUT DETECTOR
# ══════════════════════════════════════════════
with tab2:
    st.subheader("🔍 Agricultural Input Validator")
    st.caption("Calls `POST /api/v1/validate` — checks crop, region and date for anomalies.")

    with st.form("validator_form"):
        vc1, vc2, vc3 = st.columns(3)
        v_crop   = vc1.selectbox("🌽 Crop",   available_crops, key="v_crop")
        v_region = vc2.text_input("📍 Region", value=market, key="v_region")
        v_date   = vc3.date_input("📅 Date",   value=datetime.today(), key="v_date")
        submitted = st.form_submit_button("🔎 Validate Input", type="primary", use_container_width=True)

    if submitted:
        payload = {
            "crop":   v_crop.lower(),
            "region": v_region,
            "date":   str(v_date),
        }
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
            r1.metric("Valid?",    "✅ Yes" if is_valid else "❌ No")
            r2.metric("Flagged?",  "🚩 Yes" if is_fake  else "✅ No")
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
                    payload = {"crop": str(row["crop"]).lower(),
                               "region": str(row["region"]),
                               "date": str(row["date"])}
                    res, _ = api("POST", "/api/v1/validate", base_url, json=payload)
                    if res:
                        results.append({**row.to_dict(),
                                        "valid": res.get("is_valid"),
                                        "flagged": res.get("is_fake"),
                                        "confidence": f"{res.get('confidence',0)*100:.0f}%"})
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

    # ── Price Movers
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
                    unsafe_allow_html=True
                )
            st.markdown("")
            for l in losers:
                st.markdown(
                    f'<div class="alert-high">📉 <b>{l["commodity"]}</b> in {l["market"]} '
                    f'→ {l["change_pct"]:.1f}% ({ugx(l["latest_price"])})</div>',
                    unsafe_allow_html=True
                )

    # ── Cross-market comparison for chosen crop
    with mi_c2:
        st.markdown(f"#### 🗺️ {crop} — Cross-Market Prices")
        summary_data, summary_err = api("GET", f"/markets/summary/{crop}", base_url)
        if summary_err:
            st.error(summary_err)
        elif summary_data:
            mkts = summary_data.get("markets", [])
            if mkts:
                df_mkts = pd.DataFrame([{
                    "Market":  m["market"],
                    "Price (UGX)": m["latest_price"],
                    "30d Chg %": m.get("price_change_pct") or 0,
                    "Trend": m.get("trend", "—"),
                    "Data pts": m.get("data_points", 0),
                } for m in mkts])
                bar_fig = go.Figure(go.Bar(
                    y=df_mkts["Market"],
                    x=df_mkts["Price (UGX)"],
                    orientation="h",
                    marker_color=["#00cc66" if t == "rising" else
                                  "#ff4c4c" if t == "falling" else "#f0a500"
                                  for t in df_mkts["Trend"]],
                    text=[f"{ugx(p)}" for p in df_mkts["Price (UGX)"]],
                    textposition="outside",
                ))
                bar_fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=320,
                    margin=dict(l=10, r=40, t=10, b=10),
                    xaxis_title="UGX / kg",
                )
                st.plotly_chart(bar_fig, use_container_width=True)
                rec = summary_data.get("recommendation", "")
                if rec:
                    st.info(f"💡 **{rec}**")

    # ── Arbitrage
    st.markdown("---")
    st.markdown(f"#### ⚡ Arbitrage Opportunities — {crop}")
    arb_data, arb_err = api("GET", f"/markets/arbitrage/{crop}?min_margin_pct=10", base_url)
    if arb_err:
        st.warning(f"Arbitrage data unavailable: {arb_err}")
    elif arb_data:
        arb_df = pd.DataFrame([{
            "Buy in":    a["buy_market"],
            "Sell in":   a["sell_market"],
            "Buy (UGX)": ugx(a["buy_price"]),
            "Sell (UGX)":ugx(a["sell_price"]),
            "Gross Margin": f'{a["gross_margin_pct"]:.1f}%',
            "Viable?":   "✅" if a["viable"] else "⚠️",
            "Note":      a["note"],
        } for a in arb_data])
        st.dataframe(arb_df, use_container_width=True, height=220)
    else:
        st.info(f"No arbitrage opportunities found for {crop} above 10% margin.")


# ══════════════════════════════════════════════
# TAB 4 — NATIONAL OVERVIEW
# ══════════════════════════════════════════════
with tab4:
    st.subheader("🗺️ National Price Overview")
    st.caption(f"Data as of: **{ns_data.get('data_as_of', '—') if ns_data else '—'}**")

    if ns_err:
        st.error(f"National summary unavailable: {ns_err}")
    elif ns_data:
        comms = ns_data["commodities"]
        df_ns = pd.DataFrame([{
            "Commodity":    c["commodity"],
            "Avg (UGX/kg)": c["national_avg_price"],
            "Min":          c["min_price"],
            "Max":          c["max_price"],
            "Spread %":     c["price_spread_pct"],
            "Trend":        c["trend"],
            "Markets":      c["markets_tracked"],
            "Currency":     c["currency"],
        } for c in comms])

        # Bubble chart: avg price vs spread, sized by markets tracked
        bubble_fig = px.scatter(
            df_ns,
            x="Avg (UGX/kg)",
            y="Spread %",
            size="Markets",
            color="Trend",
            text="Commodity",
            color_discrete_map={
                "rising":  "#00cc66",
                "falling": "#ff4c4c",
                "stable":  "#f0a500",
            },
            template="plotly_dark",
            height=400,
            title="National Price Landscape — Avg Price vs Market Spread",
        )
        bubble_fig.update_traces(textposition="top center", marker=dict(sizemin=10))
        bubble_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(bubble_fig, use_container_width=True)

        # Full table with trend icons
        def trend_emoji(t):
            return {"rising": "📈 Rising", "falling": "📉 Falling", "stable": "➡️ Stable"}.get(t, t)

        df_display = df_ns.copy()
        df_display["Trend"] = df_display["Trend"].apply(trend_emoji)
        df_display["Avg (UGX/kg)"] = df_display["Avg (UGX/kg)"].apply(lambda x: f"{x:,.0f}")
        df_display["Min"] = df_display["Min"].apply(lambda x: f"{x:,.0f}")
        df_display["Max"] = df_display["Max"].apply(lambda x: f"{x:,.0f}")
        df_display["Spread %"] = df_display["Spread %"].apply(lambda x: f"{x:.1f}%")
        st.dataframe(df_display.drop(columns=["Currency"]), use_container_width=True, height=350)

    # Market Overview picker
    st.markdown("---")
    st.markdown("#### 🏪 Full Market Overview")
    ov_col, ov_btn = st.columns([3, 1])
    ov_market = ov_col.selectbox("Choose market", available_markets, key="ov_mkt")
    run_ov    = ov_btn.button("Load", use_container_width=True)
    if run_ov:
        ov_data, ov_err = api("GET", f"/markets/overview/{ov_market}", base_url)
        if ov_err:
            st.error(ov_err)
        elif ov_data:
            st.markdown(f"**{ov_market}** — {ov_data.get('total_commodities_tracked', 0)} commodities tracked")
            ov_df = pd.DataFrame(ov_data.get("commodities", []))
            if not ov_df.empty:
                ov_df["latest_price"] = ov_df["latest_price"].apply(lambda x: f"{x:,.0f}")
                ov_df["trend"] = ov_df["trend"].apply(trend_emoji)
                st.dataframe(ov_df, use_container_width=True)

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.divider()
st.caption(
    "AgriGuard • Agricultural Intelligence System • "
    "Built by Keith Ndiema Kissa (2025/BCS/101/PS), MUST • "
    "For Ministry of ICT & National Guidance Prototype Showcase 2026"
)