# quant/

AgriGuard's backtesting, prediction-interval, and risk-scoring layer.
Previously a scaffold (empty files); now the production implementation of
the methodology validated in `notebooks/03_walkforward_backtesting.ipynb`,
`notebooks/04_prediction_intervals_risk.ipynb`, and
`notebooks/05_model_export.ipynb` (see `notebooks/README.md` for the full
01→05 pipeline).

Shared discipline with the [Vestora](https://github.com/Ve-stora/vestora)
quant module — see the "Quant" section of `requirements.txt`
(`statsmodels`, `arch`, `mapie`, `pyarrow`).

## Layout

```
quant/
├── __init__.py
├── backtesting.py       # walk-forward CV, per tier x crop x market
├── intervals.py         # conformal-style prediction intervals per tier
├── risk_metrics.py      # commodity volatility + per-series risk score
├── model_selection.py   # XGBoost vs Prophet, chosen per crop x market
├── tests/
│   ├── __init__.py
│   ├── test_backtesting.py
│   ├── test_intervals.py
│   ├── test_risk_metrics.py
│   └── test_model_selection.py
└── README.md
```

## Pipeline

```
data/processed/features_{tier}.parquet         (notebook 02 / scripts/train_models.py)
        │
        ▼
quant.backtesting.run_backtest()
        │  → data/processed/backtest_results.parquet
        │  → data/processed/backtest_residuals.parquet   (fold-level residuals)
        │
        ├──▶ quant.intervals.add_interval_columns()       → interval_halfwidth_ugx
        ├──▶ quant.risk_metrics.build_risk_report()        → risk_scores.parquet
        └──▶ quant.model_selection.select_model_per_group() → chosen_model per series
```

## Usage

```python
from pathlib import Path
from quant.backtesting import run_backtest, summarize_by_tier
from quant.intervals import add_interval_columns
from quant.risk_metrics import build_risk_report
from quant.model_selection import select_model_per_group

processed_dir = Path("data/processed")

backtest_results, residuals = run_backtest(processed_dir)
print(summarize_by_tier(backtest_results))

with_intervals = add_interval_columns(backtest_results, residuals)
```

## Notes on production-readiness

- **`quant.backtesting.run_backtest`** retains raw fold-level residuals
  (`backtest_residuals.parquet`) — notebook 04 explicitly flags that its own
  mean/std approximation should be replaced "with the true empirical
  residual quantile from stored fold predictions" once available.
  `quant.intervals.add_interval_columns` uses the true residual quantile
  automatically wherever those residuals exist, and falls back to the
  notebook's approximation only where they don't.
- **`quant.model_selection.select_model_per_group`** runs the Prophet
  backtest per crop x market x tier for real. Notebook 05 leaves this as an
  explicit placeholder ("in a full run, `backtest_prophet` would be applied
  per group/tier here") — this module is that full run.
- All four modules import heavy ML dependencies (xgboost, prophet) lazily,
  inside the functions that need them, so `import quant` and unit tests
  that don't touch model fitting work without those packages installed.

## Testing

```bash
python -m pytest quant/tests/ -v
```

`quant/tests` is now included in `pytest.ini`'s `testpaths`, so a bare
`pytest` from the repo root runs both `tests/` and `quant/tests/`.
