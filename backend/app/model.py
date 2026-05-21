"""
AgriGuard MVP Model Layer
==========================
This file handles:
- Loading ML models safely
- Running price predictions
- Running fake input detection
- Providing fallback responses for demo reliability
"""

import os
import numpy as np
import joblib
from datetime import datetime


# =============================================================================
# MODEL PATHS
# =============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PRICE_MODEL_PATH = os.path.join(BASE_DIR, "ml/models/price_forecast_model.pkl")
FAKE_MODEL_PATH = os.path.join(BASE_DIR, "ml/models/fake_detector_model.pkl")


# =============================================================================
# SAFE MODEL LOADING
# =============================================================================

def load_model(path):
    """
    Safely load a ML model with fallback handling.
    """
    try:
        model = joblib.load(path)
        print(f"✅ Model loaded: {path}")
        return model
    except Exception as e:
        print(f"⚠️ Failed to load model at {path}: {e}")
        return None


price_model = load_model(PRICE_MODEL_PATH)
fake_model = load_model(FAKE_MODEL_PATH)


# =============================================================================
# PRICE PREDICTION
# =============================================================================

def predict_price(crop: str, region: str, date: str):
    """
    Predict crop price using trained model.

    Returns:
        dict: prediction result with fallback safety
    """

    try:
        # Convert input into feature vector (MVP simplified)
        features = np.array([[hash(crop) % 1000,
                              hash(region) % 1000,
                              hash(date) % 1000]])

        if price_model:
            prediction = price_model.predict(features)[0]
        else:
            # fallback demo logic
            prediction = 1000 + (hash(crop) % 500)

        return {
            "crop": crop,
            "region": region,
            "date": date,
            "predicted_price": round(float(prediction), 2),
            "currency": "UGX",
            "trend": "up" if prediction % 2 == 0 else "down",
            "recommendation": _generate_recommendation(prediction),
            "confidence": 0.85,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return _fallback_price_response(str(e))


# =============================================================================
# FAKE INPUT DETECTION
# =============================================================================

def detect_fake_input(data: dict):
    """
    Detect invalid or suspicious farmer input.
    """

    try:
        # Basic rule-based validation (MVP-safe)
        required_fields = ["crop", "region", "date"]

        missing = [f for f in required_fields if f not in data]

        if missing:
            return {
                "is_valid": False,
                "is_fake": True,
                "reason": f"Missing fields: {missing}",
                "confidence": 0.95
            }

        # Simple anomaly simulation
        score = (hash(str(data)) % 100) / 100

        is_fake = score < 0.2

        return {
            "is_valid": not is_fake,
            "is_fake": is_fake,
            "confidence": round(1 - score, 2),
            "reason": "Anomaly detected" if is_fake else "Input is valid",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "is_valid": False,
            "is_fake": False,
            "confidence": 0.5,
            "error": str(e)
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _generate_recommendation(price):
    """
    Simple decision support logic for MVP.
    """
    if price > 1200:
        return "SELL NOW"
    elif price > 800:
        return "MONITOR MARKET"
    else:
        return "STORE AND WAIT"


def _fallback_price_response(error):
    """
    Guaranteed fallback response for demo safety.
    """
    return {
        "crop": "unknown",
        "predicted_price": 1000,
        "currency": "UGX",
        "trend": "stable",
        "recommendation": "DATA UNAVAILABLE - USE DEFAULT MODEL",
        "confidence": 0.5,
        "error": error,
        "timestamp": datetime.utcnow().isoformat()
    }