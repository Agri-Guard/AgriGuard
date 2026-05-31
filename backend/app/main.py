"""
AgriGuard MVP FastAPI Entry Point
==================================

Purpose:
- Serve crop price predictions
- Validate farmer inputs
- Expose fake input detection
- Provide stable API for Streamlit frontend

Design principle:
👉 Maximum reliability for live demo (May 29 MVP pitch)
"""

from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import settings
from backend.app.schemas import (
    PricePredictionRequest,
    PricePredictionResponse,
    FakeInputRequest,
    FakeDetectionResponse
)

from backend.app.validator import validate_input
from backend.app.model import predict_price, detect_fake_input

from backend.app.routers.forecasts import router as forecasts_router
from backend.app.routers.markets import router as markets_router


# =============================================================================
# APP INITIALIZATION
# =============================================================================

app = FastAPI(
    title="AgriGuard MVP",
    description="AI-powered Crop Price Forecasting & Input Validation System",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(forecasts_router)
app.include_router(markets_router)


# =============================================================================
# CORS (MVP SAFE)
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP: avoid config failures
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# GLOBAL ERROR HANDLER (PREVENT DEMO CRASHES)
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# =============================================================================
# HEALTH CHECK (FOR DEMO CONFIDENCE)
# =============================================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": "AgriGuard MVP",
        "version": settings.app_version,
        "ml_ready": True,
        "validator_ready": True,
        "fake_detector_ready": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


# =============================================================================
# ROOT
# =============================================================================

@app.get("/")
def root():
    return {
        "message": "Welcome to AgriGuard MVP API",
        "docs": "/docs",
        "health": "/health"
    }


# =============================================================================
# PRICE PREDICTION ENDPOINT (CORE MVP FEATURE)
# =============================================================================

@app.post("/api/v1/predict", response_model=PricePredictionResponse)
def predict_price_endpoint(payload: PricePredictionRequest):

    # Step 1: Validate input
    validation = validate_input(payload.dict())

    if not validation["is_valid"]:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid input",
                "details": validation["errors"],
                "confidence": validation["confidence"]
            }
        )

    # Step 2: Run ML prediction
    result = predict_price(
        crop=payload.crop,
        region=payload.region,
        date=payload.date
    )

    return result


# =============================================================================
# FAKE INPUT DETECTION ENDPOINT (TRUST LAYER)
# =============================================================================

@app.post("/api/v1/validate", response_model=FakeDetectionResponse)
def fake_detection_endpoint(payload: FakeInputRequest):

    result = detect_fake_input(payload.dict())

    return result