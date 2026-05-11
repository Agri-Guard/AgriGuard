"""
config.py — AgriGuard Application Configuration
=================================================
Central settings module. Every other file imports from here.

Uses Pydantic's BaseSettings to:
  - Read values from environment variables automatically
  - Fall back to .env file if env vars aren't set
  - Validate types at startup (fail fast before any DB connection)
  - Provide sensible defaults for local development

Setup:
    1. Copy config/env.example to config/.env
    2. Fill in your actual values (DB password, etc.)
    3. Never commit .env to Git — it's in .gitignore

Usage (in any other module):
    from app.config import settings

    engine = create_engine(settings.database_url)
    print(settings.app_name)

Author: AgriGuard Team
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, computed_field


# =============================================================================
# PATH CONSTANTS
# =============================================================================

# Root of the project (two levels up from this file: app/ → backend/ → agriguard/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Where .env lives — follows the skeleton's config/ folder
ENV_FILE = PROJECT_ROOT / "config" / ".env"

# Data directories (matches the project skeleton)
DATA_DIR         = PROJECT_ROOT / "data"
RAW_DATA_DIR     = DATA_DIR / "raw"
PROCESSED_DIR    = DATA_DIR / "processed"
SEEDS_DIR        = DATA_DIR / "seeds"
ML_MODELS_DIR    = PROJECT_ROOT / "ml" / "saved_models"


# =============================================================================
# MAIN SETTINGS CLASS
# =============================================================================

class Settings(BaseSettings):
    """
    All application settings in one place.

    Pydantic reads these from environment variables first.
    If not found, it falls back to the .env file.
    If still not found, it uses the default= value below.

    Variable names are case-insensitive: APP_NAME, app_name, App_Name all work.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),          # Load from config/.env
        env_file_encoding="utf-8",
        case_sensitive=False,            # APP_NAME == app_name
        extra="ignore",                  # Don't crash on unknown env vars
    )

    # -------------------------------------------------------------------------
    # APP IDENTITY
    # -------------------------------------------------------------------------

    app_name: str = "AgriGuard"
    app_version: str = "0.1.0"
    app_description: str = (
        "Agricultural price monitoring and forecasting platform for Uganda. "
        "Built for MAAIF and smallholder farmers."
    )

    # "development", "staging", or "production"
    # Controls logging level, debug mode, CORS strictness
    environment: str = "development"

    # Set to False in production — disables /docs and /redoc Swagger UI
    debug: bool = True

    # -------------------------------------------------------------------------
    # DATABASE — PostgreSQL via SQLAlchemy
    # -------------------------------------------------------------------------

    # Individual DB connection parts (used to build the URL below)
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "agriguard"
    db_user: str = "postgres"
    db_password: str = "postgres"          # CHANGE THIS in .env for production

    # Optional: override the full URL directly (useful for cloud DBs like Supabase)
    # If set, this takes priority over the individual parts above
    database_url_override: Optional[str] = None

    @computed_field
    @property
    def database_url(self) -> str:
        """
        Builds the full SQLAlchemy-compatible PostgreSQL connection string.

        If DATABASE_URL_OVERRIDE is set in .env, use that directly.
        This is useful for Heroku, Railway, Supabase, or any cloud DB
        that gives you a connection string directly.

        Otherwise, build it from the individual parts.

        Format: postgresql+psycopg2://user:password@host:port/dbname
        The +psycopg2 part tells SQLAlchemy to use the psycopg2 driver.
        """
        if self.database_url_override:
            return self.database_url_override

        return (
            f"postgresql+psycopg2://"
            f"{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}"
            f"/{self.db_name}"
        )

    @computed_field
    @property
    def async_database_url(self) -> str:
        """
        Async version of the DB URL using asyncpg driver.
        Used if you later switch to async SQLAlchemy (FastAPI best practice).
        asyncpg is significantly faster than psycopg2 for async workloads.
        """
        base = self.database_url.replace("postgresql+psycopg2://", "")
        return f"postgresql+asyncpg://{base}"

    # SQLAlchemy connection pool settings
    # For an MVP with light traffic, these defaults are fine
    db_pool_size: int = 5           # Number of persistent connections
    db_max_overflow: int = 10       # Extra connections allowed under load
    db_pool_timeout: int = 30       # Seconds to wait for a connection
    db_echo_sql: bool = False       # Set True to log all SQL (useful for debugging)

    # -------------------------------------------------------------------------
    # SECURITY
    # -------------------------------------------------------------------------

    # Secret key for signing JWT tokens — generate with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    # MUST be changed in production. Never commit the real value.
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_SECRETS_TOKEN_HEX_32"

    # JWT token expiry in minutes (default: 24 hours)
    access_token_expire_minutes: int = 1440

    # Hashing algorithm for JWT
    algorithm: str = "HS256"

    # -------------------------------------------------------------------------
    # CORS — Cross-Origin Resource Sharing
    # Controls which frontends can call this API
    # -------------------------------------------------------------------------

    # In development, allow all origins
    # In production, set this to your actual frontend domain(s)
    cors_origins: list[str] = [
        "http://localhost:3000",       # React dev server
        "http://localhost:5173",       # Vite dev server
        "http://127.0.0.1:3000",
    ]

    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["*"]

    # -------------------------------------------------------------------------
    # API SERVER
    # -------------------------------------------------------------------------

    api_host: str = "0.0.0.0"        # Listen on all interfaces
    api_port: int = 8000
    api_prefix: str = "/api/v1"       # All routes prefixed: /api/v1/prices, etc.

    # Number of Uvicorn worker processes
    # Rule of thumb: (2 × CPU cores) + 1
    # For MVP on a 2-core server: 5 workers
    workers: int = 1                   # Keep at 1 for development

    # -------------------------------------------------------------------------
    # EXTERNAL APIS
    # -------------------------------------------------------------------------

    # Open-Meteo — completely free, no key needed
    # Docs: https://open-meteo.com/en/docs
    openmeteo_base_url: str = "https://archive-api.open-meteo.com/v1/archive"
    openmeteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"

    # USSD gateway (for farmer SMS/USSD price queries)
    # Africa's Talking is the most common provider in Uganda
    africastalking_api_key: Optional[str] = None
    africastalking_username: Optional[str] = None
    africastalking_shortcode: Optional[str] = None   # e.g. "*123#"

    # -------------------------------------------------------------------------
    # ML MODEL SETTINGS
    # -------------------------------------------------------------------------

    # Which model file to load for price forecasting
    # Relative to ml/saved_models/
    active_forecast_model: str = "forecast_model_latest.pkl"

    # How many days ahead to forecast
    forecast_horizon_days: int = 14

    # Minimum confidence score to include a forecast in API response
    # Below this, the API returns a warning instead of a number
    min_forecast_confidence: float = 0.60

    # -------------------------------------------------------------------------
    # LOGGING
    # -------------------------------------------------------------------------

    log_level: str = "INFO"           # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_format: str = "json"          # "json" for production, "text" for dev

    # -------------------------------------------------------------------------
    # VALIDATORS — run at startup to catch config mistakes early
    # -------------------------------------------------------------------------

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is one of the allowed values."""
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"environment must be one of: {allowed}. Got: '{v}'")
        return v.lower()

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """
        Warn loudly if the default secret key is used in production.
        This prevents the classic "forgot to change the secret" mistake.
        """
        if v == "CHANGE_ME_IN_PRODUCTION_USE_SECRETS_TOKEN_HEX_32":
            # Only a warning in dev — hard fail would be too annoying
            import warnings
            warnings.warn(
                "⚠️  Using default SECRET_KEY. "
                "Run: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "and set the result in config/.env",
                stacklevel=2,
            )
        return v

    @field_validator("db_port")
    @classmethod
    def validate_db_port(cls, v: int) -> int:
        """PostgreSQL default is 5432. Flag unusual ports."""
        if not (1 <= v <= 65535):
            raise ValueError(f"DB port must be between 1 and 65535. Got: {v}")
        return v

    # -------------------------------------------------------------------------
    # CONVENIENCE PROPERTIES
    # -------------------------------------------------------------------------

    @computed_field
    @property
    def is_production(self) -> bool:
        """Shorthand for checking if we're in production."""
        return self.environment == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        """Shorthand for dev mode."""
        return self.environment == "development"

    @computed_field
    @property
    def ml_model_path(self) -> Path:
        """Full path to the active ML model file."""
        return ML_MODELS_DIR / self.active_forecast_model

    def display(self) -> None:
        """
        Print a safe summary of current settings to the console.
        Masks sensitive values (passwords, API keys, secret keys).
        Useful to call at app startup to confirm correct configuration.
        """
        print(f"\n{'='*50}")
        print(f"  {self.app_name} v{self.app_version}")
        print(f"{'='*50}")
        print(f"  Environment : {self.environment}")
        print(f"  Debug mode  : {self.debug}")
        print(f"  API         : http://{self.api_host}:{self.api_port}{self.api_prefix}")
        print(f"  Database    : {self.db_host}:{self.db_port}/{self.db_name}")
        print(f"  DB password : {'*' * len(self.db_password)}")  # masked
        print(f"  Secret key  : {'*' * 8}...{self.secret_key[-4:]}")  # show last 4
        print(f"  Log level   : {self.log_level}")
        print(f"  ML model    : {self.active_forecast_model}")
        print(f"{'='*50}\n")


# =============================================================================
# SINGLETON — cached so settings are only loaded once per process
# =============================================================================

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the application settings instance.

    @lru_cache ensures this is only instantiated once — the .env file
    is read once at startup, not on every request.

    FastAPI dependency injection usage:
        from fastapi import Depends
        from app.config import get_settings, Settings

        @router.get("/info")
        def app_info(settings: Settings = Depends(get_settings)):
            return {"version": settings.app_version}

    Direct usage (anywhere else):
        from app.config import settings
        print(settings.database_url)
    """
    return Settings()


# Module-level singleton — most files just do: from app.config import settings
settings = get_settings()