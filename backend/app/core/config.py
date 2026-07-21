"""
AgriGuard configuration.
Reads from (in priority order):
  1. Environment variables
  2. backend/.env
  3. config/.env
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]

# Load .env files — later calls override earlier ones (env vars win over files)
for env_path in [ROOT / "config" / ".env", ROOT / "backend" / ".env"]:
    if env_path.exists():
        load_dotenv(env_path, override=False)


class Settings:
    # app
    app_name:   str  = "AgriGuard"
    app_version: str = "0.1.0"
    app_env:    str  = os.getenv("APP_ENV",    "development")
    debug:      bool = os.getenv("DEBUG",      "false").lower() == "true"
    secret_key: str  = os.getenv("SECRET_KEY", "dev-secret-key")
    log_level:  str  = os.getenv("LOG_LEVEL",  "INFO")

    # backend
    backend_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))
    backend_url:  str = os.getenv("BACKEND_URL",  "http://localhost:8000")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:8501")

    # data / models
    price_data_path: str = os.getenv(
        "AGRIGUARD_PRICE_DATA",
        str(ROOT / "data" / "raw" / "wfp_food_prices_uga.csv"),
    )
    model_dir: str = os.getenv("MODEL_DIR", str(ROOT / "ml" / "models"))

    # Anthropic
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # database (optional)
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./agriguard_dev.db",   # SQLite fallback for dev
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def has_anthropic_key(self) -> bool:
        return bool(self.anthropic_api_key and not self.anthropic_api_key.startswith("sk-ant-..."))


settings = Settings()