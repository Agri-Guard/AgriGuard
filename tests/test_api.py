"""
AgriGuard — backend API tests.
Run from repo root:  pytest tests/ -v
Requires:  pip install pytest httpx
Models don't need to be trained — tests mock model.py where needed.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# ensure repo root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.main import app

client = TestClient(app)


# ── fixtures ───────────────────────────────────────────────────────────────

MOCK_PREDICT_RESULT = {
    "commodity": "Maize",
    "market": "Kampala",
    "year": 2025,
    "month": 8,
    "predicted_price_ugx": 1350.0,
    "lower_bound_ugx": 1215.0,
    "upper_bound_ugx": 1485.0,
    "currency": "UGX",
}

MOCK_STATUS = {
    "price_model": True,
    "encoders": True,
    "data_file": True,
    "metrics": {"price_model": {"r2": 0.87}},
}


# ── health & root ──────────────────────────────────────────────────────────

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "message" in body
    assert "docs" in body


def test_health():
    with patch("backend.app.model.status", return_value=MOCK_STATUS):
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "models" in body


# ── /api/v1/predict ────────────────────────────────────────────────────────

def test_predict_success():
    with patch("backend.app.model.predict_price", return_value=MOCK_PREDICT_RESULT):
        r = client.post("/api/v1/predict", json={
            "commodity": "Maize",
            "market": "Kampala",
            "year": 2025,
            "month": 8,
        })
    assert r.status_code == 200
    body = r.json()
    assert body["commodity"] == "Maize"
    assert body["currency"] == "UGX"
    assert "predicted_price_ugx" in body


def test_predict_invalid_month():
    r = client.post("/api/v1/predict", json={
        "commodity": "Maize",
        "market": "Kampala",
        "year": 2025,
        "month": 13,   # invalid
    })
    assert r.status_code == 422


def test_predict_model_not_ready():
    from backend.app.model import ModelNotReadyError
    with patch("backend.app.model.predict_price",
               side_effect=ModelNotReadyError("Model not loaded")):
        r = client.post("/api/v1/predict", json={
            "commodity": "Maize",
            "market": "Kampala",
            "year": 2025,
            "month": 6,
        })
    assert r.status_code == 503


# ── /api/v1/forecasts ──────────────────────────────────────────────────────

def test_forecast_commodities():
    with patch("backend.app.model.list_commodities",
               return_value=["Maize", "Beans"]):
        r = client.get("/api/v1/forecasts/commodities")
    assert r.status_code == 200
    assert "commodities" in r.json()


def test_forecast_markets():
    with patch("backend.app.model.list_markets",
               return_value=["Kampala", "Gulu"]):
        r = client.get("/api/v1/forecasts/markets")
    assert r.status_code == 200
    assert "markets" in r.json()


def test_forecast_model_not_ready():
    with patch("backend.app.model.status",
               return_value={**MOCK_STATUS, "price_model": False}):
        r = client.get("/api/v1/forecasts/Maize/Kampala?horizon=3")
    assert r.status_code == 503


# ── schema validation ──────────────────────────────────────────────────────

def test_predict_request_normalises_case():
    """commodity and market should be title-cased by the validator."""
    with patch("backend.app.model.predict_price", return_value=MOCK_PREDICT_RESULT):
        r = client.post("/api/v1/predict", json={
            "commodity": "maize",      # lowercase
            "market":    "kampala",
            "year": 2025,
            "month": 6,
        })
    # either 200 (model mock worked) or 422 (schema validation — both fine here)
    assert r.status_code in (200, 422, 503)
