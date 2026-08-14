"""
CLI entry point: trains the price forecaster from the WFP CSV, saves
.pkl artifacts to ml/models/, and writes ml/models/metrics.json.

This replaces the top-level scripts/train_models.py referenced in the
README with a version that lives next to the model code it trains,
so features/config/models can't drift out of sync with the script
that produces them.

Run from repo root:
    python -m backend.ml.train

Expects data/raw/wfp_food_prices_uga.csv to already exist -- run
scripts/download_wfp_data.py first if it doesn't.
"""
import json
from datetime import datetime, timezone

import pandas as pd

from .config import DATA_PATH, METRICS_PATH, MODELS_DIR, PRICE_MODEL_PATH
from .price_forecast_model import PriceForecastModel


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} not found -- run scripts/download_wfp_data.py first"
        )

    print(f"Loading price history from {DATA_PATH}")
    raw_df = pd.read_csv(DATA_PATH, parse_dates=["date"])

    print("Training price forecast model (XGBoost)...")
    forecaster = PriceForecastModel()
    price_metrics = forecaster.train(raw_df)
    forecaster.save(PRICE_MODEL_PATH)
    print(f"  MAE={price_metrics['mae']:.1f}  MAPE={price_metrics['mape']:.3f}  R2={price_metrics['r2']:.3f}")

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "price_forecast": price_metrics,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"Wrote metrics to {METRICS_PATH}")


if __name__ == "__main__":
    main()
