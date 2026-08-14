"""
AgriGuard MVP FastAPI Entry Point
==================================

Purpose:
- Serve crop price predictions and conveyance
- Validate farmer inputs
- Provide stable API for Streamlit frontend

Design principle:
👉 Maximum reliability for live demo
"""

from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.schemas import (
    PricePredictionRequest,
    PricePredictionResponse,
)

from backend.app.validator import validate_input
from backend.app.model import predict_price, ModelNotReadyError

from backend.app.routers.forecasts import router as forecasts_router
from backend.app.routers.markets import router as markets_router
from backend.app.routers.ussd import router as ussd_router

# NOTE: routers/prices.py is intentionally NOT wired in yet. It depends on a
# separate, still-broken layer (app/database.py, app/services/price_service.py,
# app/models/price.py) that imports a nonexistent top-level `app` package and
# assumes a Postgres service this docker-compose doesn't define. That's a
# bigger fix than this pass covers — see README "Known issues".


# =============================================================================
# APP INITIALIZATION
# =============================================================================

app = FastAPI(
    title="AgriGuard MVP",
    description="AI-powered Crop Price Forecasting, Conveyance & Market Intelligence System",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(forecasts_router)
app.include_router(markets_router)
app.include_router(ussd_router)


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

    # Step 2: parse "YYYY-MM-DD" into the year/month predict_price expects
    try:
        target_date = datetime.strptime(payload.date, "%Y-%m-%d")
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid input", "details": ["date must be YYYY-MM-DD"]},
        )

    # Step 3: run ML prediction (model.py works in commodity/market terms)
    try:
        result = predict_price(
            commodity=payload.crop,
            market=payload.region,
            year=target_date.year,
            month=target_date.month,
        )
    except ModelNotReadyError as e:
        return JSONResponse(status_code=503, content={"error": "Model not ready", "detail": str(e)})
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": "Invalid input", "detail": str(e)})

    # Step 4: adapt model.py's output shape into the PricePredictionResponse the API promises
    predicted = result["predicted_price_ugx"]
    lag1 = result.get("price_lag1", predicted)
    if predicted > lag1 * 1.02:
        trend, recommendation = "up", "STORE"
    elif predicted < lag1 * 0.98:
        trend, recommendation = "down", "SELL"
    else:
        trend, recommendation = "stable", "HOLD"

    # ±10% heuristic interval (see model.py) -> narrower interval = higher confidence
    interval_width = (result["upper_bound_ugx"] - result["lower_bound_ugx"]) / predicted if predicted else 1.0
    confidence = max(0.0, min(1.0, 1 - interval_width))

    return PricePredictionResponse(
        crop=payload.crop,
        region=payload.region,
        date=payload.date,
        predicted_price=predicted,
        currency=result["currency"],
        trend=trend,
        recommendation=recommendation,
        confidence=round(confidence, 2),
        timestamp=datetime.utcnow(),
    )
