"""
AgriGuard MVP Schemas
=====================
Defines all request/response structures for the API.

Purpose:
- Ensure frontend and backend speak the same language
- Prevent invalid data from reaching ML models
- Keep API responses consistent for demo reliability
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class PricePredictionRequest(BaseModel):
    """
    Input for crop price prediction.
    """

    crop: str = Field(..., example="maize")
    region: str = Field(..., example="Mbarara")
    date: str = Field(..., example="2026-06-01")


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class PricePredictionResponse(BaseModel):
    """
    Output from price prediction model.
    """

    crop: str
    region: str
    date: str

    predicted_price: float
    currency: str = "UGX"

    trend: str  # "up" | "down" | "stable"
    recommendation: str  # SELL / HOLD / STORE

    confidence: float = Field(..., ge=0, le=1)

    timestamp: datetime


# =============================================================================
# GENERIC SYSTEM RESPONSE (OPTIONAL BUT USEFUL FOR /health etc.)
# =============================================================================

class HealthResponse(BaseModel):
    """
    System health status response.
    """

    status: str
    version: str
    ml_ready: bool
    timestamp: datetime
