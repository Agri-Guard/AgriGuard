"""
AgriGuard — Fake Agro-Input Detector page
Calls POST /api/v1/validate
"""

import os
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="Fake Detector | AgriGuard",
    page_icon="🔍",
    layout="centered",
)
st.title("🔍 Fake Agro-Input Detector")
st.caption(
    "Checks whether seeds, pesticides, or fertilizers show signs of counterfeiting. "
    "Score each attribute honestly for an accurate result."
)


# ── helpers ────────────────────────────────────────────────────────────────

RISK_COLOR = {"LOW": "green", "MEDIUM": "orange", "HIGH": "red"}
RISK_ICON  = {"LOW": "✅", "MEDIUM": "⚠️", "HIGH": "🚨"}


def post_validate(payload: dict):
    try:
        r = requests.post(
            f"{BACKEND_URL}/api/v1/validate",
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot reach backend at `{BACKEND_URL}`. Is it running?")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ── form ───────────────────────────────────────────────────────────────────

st.subheader("Product Details")

product_name = st.text_input(
    "Product name / batch code",
    placeholder="e.g. Longe 10H Maize Seed — Batch UG-2024-001",
)

st.divider()
st.subheader("Physical Inspection Scores")
st.caption("Rate each attribute based on what you observe.")

col1, col2 = st.columns(2)

with col1:
    label_quality = st.slider(
        "Label quality (0=poor, 10=excellent)",
        0.0, 10.0, 8.0, 0.5,
        help="Clarity of print, correct fonts, no spelling errors.",
    )
    seal_integrity = st.slider(
        "Seal / packaging integrity (0–10)",
        0.0, 10.0, 9.0, 0.5,
        help="Tamper-evident seal intact, no tears or re-gluing.",
    )
    visual_anomaly = st.slider(
        "Visual anomaly score (0=none, 10=many)",
        0.0, 10.0, 1.0, 0.5,
        help="Discolouration, unusual texture, incorrect branding placement.",
    )
    weight_deviation = st.slider(
        "Weight deviation from stated weight (%)",
        0.0, 50.0, 2.0, 0.5,
        help="0% = exactly right. High deviation is suspicious.",
    )

with col2:
    seller_rating = st.slider(
        "Seller / agro-dealer rating (1–5)",
        1.0, 5.0, 4.0, 0.5,
        help="Your trust rating for the seller.",
    )
    price_deviation = st.slider(
        "Price below market rate (%)",
        0.0, 80.0, 3.0, 1.0,
        help="0% = market price. Very cheap products are often fake.",
    )
    barcode_valid = st.radio(
        "Barcode / QR scans correctly?",
        options=[1, 0],
        format_func=lambda x: "Yes" if x else "No",
        horizontal=True,
    )
    batch_code_valid = st.radio(
        "Batch code verifiable with supplier?",
        options=[1, 0],
        format_func=lambda x: "Yes" if x else "No / Not checked",
        horizontal=True,
    )

st.divider()

# ── submit ─────────────────────────────────────────────────────────────────
if st.button("🔍 Check Product", type="primary", use_container_width=True):
    if not product_name.strip():
        st.warning("Please enter a product name.")
        st.stop()

    payload = {
        "product_name":         product_name.strip(),
        "weight_deviation_pct": weight_deviation,
        "label_quality_score":  label_quality,
        "seal_integrity_score": seal_integrity,
        "barcode_valid":        barcode_valid,
        "seller_rating":        seller_rating,
        "price_deviation_pct":  price_deviation,
        "batch_code_valid":     batch_code_valid,
        "visual_anomaly_score": visual_anomaly,
    }

    with st.spinner("Analysing product …"):
        result = post_validate(payload)

    if result:
        risk   = result["risk_level"]
        icon   = RISK_ICON[risk]
        color  = RISK_COLOR[risk]
        verdict = "LIKELY COUNTERFEIT" if result["is_fake"] else "APPEARS GENUINE"

        st.divider()
        st.subheader("Result")

        # big verdict banner
        st.markdown(
            f"""
            <div style="
                background: {'#ffdddd' if result['is_fake'] else '#ddffdd'};
                border-left: 6px solid {color};
                padding: 16px 20px; border-radius: 8px;
                font-size: 20px; font-weight: bold;
            ">
            {icon} {verdict} &nbsp;|&nbsp; Risk: <span style="color:{color}">{risk}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")
        c1, c2, c3 = st.columns(3)
        c1.metric("Fake Probability",    f"{result['fake_probability']*100:.1f}%")
        c2.metric("Genuine Probability", f"{result['genuine_probability']*100:.1f}%")
        c3.metric("Confidence",          f"{result['confidence']*100:.1f}%")

        st.info(f"**Recommendation:** {result['recommendation']}")

        # probability bar
        st.progress(
            result["fake_probability"],
            text=f"Counterfeit likelihood: {result['fake_probability']*100:.1f}%",
        )

# ── guidance ───────────────────────────────────────────────────────────────
with st.expander("ℹ️ How to score each attribute"):
    st.markdown("""
| Attribute | Genuine signs | Counterfeit signs |
|---|---|---|
| Label quality | Sharp print, correct logo, no typos | Blurry, wrong fonts, misspellings |
| Seal integrity | Unbroken tamper seal | Torn, re-stuck, or missing seal |
| Barcode | Scans to manufacturer website | Doesn't scan or links to wrong site |
| Weight | Within 2–3% of stated weight | More than 10% off |
| Price | Near market rate | Suspiciously cheap (>20% below market) |
| Seller rating | Registered agro-dealer | Unknown, roadside, or unverified |
| Batch code | Matches supplier records | Doesn't match or supplier uncontactable |
| Visual anomaly | Uniform colour, correct texture | Discolouration, clumping, odd smell |
    """)
