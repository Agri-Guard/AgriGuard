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
    uvicorn app.main:app --reload --port 8000

    # Production
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

Then open: http://localhost:8000/docs  ← Swagger UI (auto-generated)
           http://localhost:8000/redoc ← ReDoc UI

Author: AgriGuard Team
"""

from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import settings
from app.database import check_db_connection, engine
from app.models.price import init_db

# Import all routers — add more here as the app grows
from app.routers import prices, markets, forecasts, ussd


# =============================================================================
# APP INSTANCE
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,

    # Swagger UI only available in non-production
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)


# =============================================================================
# MIDDLEWARE — runs on every request/response
# =============================================================================

# CORS — controls which origins (frontends) can call this API
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
    - Prints config summary
    - Creates DB tables (safe to call even if tables exist)
    - Confirms DB connectivity
    """
    settings.display()

    # Create tables — uses CREATE TABLE IF NOT EXISTS internally
    # For production migrations, replace with Alembic
    try:
        init_db(engine)
    except OperationalError as e:
        print(f"⚠️  Could not create DB tables: {e}")
        print("   Check your DATABASE_URL in config/.env")

    # Confirm DB is reachable
    if check_db_connection():
        print("✅ Database connection: OK\n")
    else:
        print("❌ Database connection: FAILED — check config/.env\n")


@app.on_event("shutdown")
async def on_shutdown():
    """Runs when the server shuts down. Dispose the connection pool cleanly."""
    engine.dispose()
    print("👋 AgriGuard server shut down. Connection pool closed.")


# =============================================================================
# GLOBAL EXCEPTION HANDLERS
# Catch DB errors and return clean JSON — never expose raw SQL errors
# =============================================================================

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """
    Catches SQLAlchemy IntegrityError (unique constraint violations, etc.)
    and returns a readable 409 Conflict instead of a 500 traceback.
    """
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "Data conflict",
            "detail": "A record with these values already exists.",
            "hint": "Check for duplicate crop/market/date/unit combinations.",
        },
    )


@app.exception_handler(OperationalError)
async def db_error_handler(request: Request, exc: OperationalError):
    """
    Catches DB connectivity errors (DB down, wrong password, etc.)
    Returns 503 Service Unavailable — tells the client to retry.
    """
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Database unavailable",
            "detail": "Could not connect to the database. Please try again shortly.",
        },
    )


# =============================================================================
# CORE ROUTES (not versioned — always available)
# =============================================================================

@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    description="Used by load balancers and monitoring tools to verify the API is up.",
)
def health_check():
    """
    Returns app status and DB connectivity.
    Returns 200 if healthy, 503 if DB is unreachable.

    Example response:
        {
            "status": "ok",
            "version": "0.1.0",
            "environment": "development",
            "db_connected": true,
            "timestamp": "2024-03-15T10:30:00"
        }
    """
    db_ok = check_db_connection()

    return JSONResponse(
        status_code=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
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
    """Root redirect — tells developers where the docs are."""
    return {
        "message": f"Welcome to {settings.app_name} API v{settings.app_version}",
        "docs": "/docs",
        "health": "/health",
    }


# =============================================================================
# VERSIONED API ROUTERS
# All routes prefixed with /api/v1 (from settings.api_prefix)
# =============================================================================

API = settings.api_prefix   # "/api/v1"

app.include_router(prices.router,    prefix=API)   # /api/v1/prices/...
app.include_router(markets.router,   prefix=API)   # /api/v1/markets/...
app.include_router(forecasts.router, prefix=API)   # /api/v1/forecasts/...
app.include_router(ussd.router,      prefix=API)   # /api/v1/ussd/...