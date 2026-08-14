# ml/

Home for training runs, evaluation reports, and saved model
artifacts. Kept separate from `backend/ml/` on purpose:

- **`backend/ml/`** — the importable Python package (feature
  engineering, model classes, `train.py`). This is what the FastAPI
  backend imports for inference.
- **`ml/`** (this directory) — where you actually *run* training and
  evaluation, and where the resulting artifacts land. Nothing in here
  is imported by the backend at runtime; it's the workspace around
  the package.

## Layout

```
ml/
├── training/
│   ├── train_price_model.py     # CLI: train + save the XGBoost forecaster
│   └── evaluate.py              # Backtest a saved model against held-out data
├── models/                      # Saved .pkl artifacts (gitignored) + metrics.json (committed)
└── README.md
```

## Usage

```bash
# from repo root, after scripts/download_wfp_data.py has produced data/raw/wfp_food_prices_uga.csv
python -m ml.training.train_price_model
python -m ml.training.evaluate --model ml/models/price_forecast_xgb.pkl
```

Each training script writes its artifact to `ml/models/` and appends
its metrics to `ml/models/metrics.json` rather than overwriting it,
so `metrics.json` accumulates a run history instead of only ever
showing the latest run.
