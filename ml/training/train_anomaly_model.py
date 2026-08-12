"""
Trains the Isolation Forest counterfeit input detector and saves it
to ml/models/.

Thin CLI wrapper around backend.ml.anomaly_detector -- see
train_price_model.py for why the model logic lives in the backend
package rather than here.

Run from repo root:
    python -m ml.training.train_anomaly_model
"""
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.ml.anomaly_detector import CounterfeitInputDetector  # noqa: E402
from backend.ml.features import build_feature_matrix  # noqa: E402
from ml.training.metrics_log import append_run  # noqa: E402

DATA_PATH = REPO_ROOT / "data" / "raw" / "wfp_food_prices_uga.csv"
OUTPUT_PATH = REPO_ROOT / "ml" / "models" / "counterfeit_detector.pkl"


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} not found -- run scripts/download_wfp_data.py first"
        )

    print(f"Loading {DATA_PATH}")
    raw_df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    feature_df, _ = build_feature_matrix(raw_df)

    detector = CounterfeitInputDetector()
    detector.train(feature_df)
    detector.save(OUTPUT_PATH)

    print(f"Saved model to {OUTPUT_PATH}")

    append_run(
        "counterfeit_detector",
        {
            "contamination": detector.model.contamination,
            "n_estimators": detector.model.n_estimators,
            "n_train_rows": int(len(feature_df)),
        },
    )


if __name__ == "__main__":
    main()