"""
main.py — AgriGuard FastAPI Application Entry Point
=====================================================
This is the file that starts everything.

It:
  1. Creates the FastAPI app instance
  2. Configures CORS (which frontends can call the API)
  3. Registers all routers (prices, markets, forecasts, ussd)
  4. Creates DB tables on startup if they don't exist
  5. Provides /health and /api/v1/info endpoints
  6. Handles global exceptions cleanly

Run the server:
    # Development (auto-reloads on file changes)
    python -m uvicorn backend.app.main:app --reload --port 8000

    # Production
    python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4

Then open:
    http://localhost:8000/docs
    http://localhost:8000/redoc

Author: AgriGuard Team
"""

from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.app.config import settings
from backend.app.database import check_db_connection, engine
from backend.app.models.price import init_db

# Import all routers
from backend.app.routers import prices, markets, forecasts, ussd


# =============================================================================
# APP INSTANCE
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,

    # Swagger docs disabled in production
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)


# =============================================================================
# MIDDLEWARE
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# =============================================================================
# STARTUP / SHUTDOWN EVENTS
# =============================================================================

@app.on_event("startup")
async def on_startup():
    """
    Runs once when the server starts.
    Creates DB tables and checks DB connection.
    """

    settings.display()

    try:
        init_db(engine)
        print("✅ Database tables initialized")
    except OperationalError as e:
        print(f"⚠️ Could not create DB tables: {e}")
        print("Check your DATABASE_URL in config/.env")

    if check_db_connection():
        print("✅ Database connection: OK\n")
    else:
        print("❌ Database connection: FAILED\n")


@app.on_event("shutdown")
async def on_shutdown():
    """
    Runs when the server shuts down.
    """

    engine.dispose()
    print("👋 AgriGuard server shut down")


# =============================================================================
# GLOBAL EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "Data conflict",
            "detail": "A record with these values already exists.",
            "hint": "Check for duplicate entries.",
        },
    )


@app.exception_handler(OperationalError)
async def db_error_handler(request: Request, exc: OperationalError):

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Database unavailable",
            "detail": "Could not connect to the database.",
        },
    )


# =============================================================================
# SYSTEM ROUTES
# =============================================================================

@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
)
def health_check():

    db_ok = check_db_connection()

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if db_ok
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "ok" if db_ok else "degraded",
            "version": settings.app_version,
            "environment": settings.environment,
            "db_connected": db_ok,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.get("/", tags=["System"], include_in_schema=False)
def root():

    return {
        "message": f"Welcome to {settings.app_name} API v{settings.app_version}",
        "docs": "/docs",
        "health": "/health",
    }


# =============================================================================
# VERSIONED API ROUTERS
# =============================================================================

API = settings.api_prefix  # "/api/v1"

app.include_router(prices.router, prefix=API)
app.include_router(markets.router, prefix=API)
app.include_router(forecasts.router, prefix=API)
app.include_router(ussd.router, prefix=API)