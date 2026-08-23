# ml/

**Last verified against the repo Aug 2026.** This directory (plus
`backend/ml/`, `quant/`, and `scripts/train_models.py`) has accumulated
**four separate price-forecasting implementations** over the project's
life. Only one of them is actually wired into the running API. This
README previously described a fifth, tidier layout that was the plan at
some point but was never what the committed code actually does — the
table below is a factual map of what's here now, not a plan.

## Which one is live?

**`scripts/train_models.py` is the only pipeline the FastAPI backend
actually uses.** It writes `ml/models/price_forecast_model.pkl` +
`ml/models/encoders.pkl`, and `backend/app/model.py` loads exactly those
two files by name at request time. If you retrain a model and don't see
it affect the API, you almost certainly trained one of the three pipelines
below instead of this one.

```bash
# from repo root, after scripts/download_wfp_data.py has produced
# data/raw/wfp_food_prices_uga.csv
python scripts/train_models.py
```

## The other three (not wired into the API)

| Pipeline | Output | Status |
|---|---|---|
| `backend/ml/` (`features.py`, `price_forecast_model.py`, `train.py`) | `ml/models/price_forecast_xgb.pkl` (single combined dict) | Complete, self-consistent, backtested by `ml/evaluation/evaluate_forecasts.py` — but `backend/app/model.py` doesn't load it. Was intended to replace `scripts/train_models.py`; that hasn't happened. |
| `ml/training/train_price_model.py` | `ml/models/{crop}_{market}_prophet.pkl` (one file per crop×market pair) | Standalone Prophet trainer, doesn't share code with any of the other three. |
| `ml/training/train_forecast.py` | `ml/saved_models/{crop}_forecast_v{N}.pkl` + `ml/evaluation/{crop}_metrics.json` | The most ambitious of the four — daily granularity, 14-day-ahead, per-crop, weather features included. Not imported or run by anything else in the repo. |

Run any of them the same way — `python -m ml.training.<script>` — but
know you're training a model nothing in the live app will pick up.

## Other files in here

- **`ml/training/feature_engineering.py`** — shared feature-engineering
  helpers. Despite an earlier version of this file's own docstring
  claiming otherwise, `scripts/train_models.py` does **not** import it —
  that script has its own inline feature engineering. Currently unused;
  kept for notebook use.
- **`ml/training/metrics_log.py`** — an `append_run()` helper meant to
  make `ml/models/metrics.json` accumulate a run history instead of
  getting overwritten each time. Not currently called by anything —
  `scripts/train_models.py` overwrites `metrics.json` with a flat dict
  each run instead of using this.
- **`ml/evaluation/evaluate_forecasts.py`** — backtests
  `backend/ml/`'s output specifically (not `scripts/train_models.py`'s).

## If you want to clean this up

Options, roughly in order of effort:
1. **Do nothing** — `scripts/train_models.py` works and is what's live;
   the other three are dormant, not broken.
2. **Retire the three dormant ones** — delete or archive them once you're
   sure nothing (a notebook, a demo, a write-up) still depends on their
   output format.
3. **Switch which one is live** — point `backend/app/model.py` at
   `backend/ml/`'s output instead (it's the cleanest of the four), retire
   `scripts/train_models.py`, and wire `metrics_log.py` /
   `feature_engineering.py` into whichever pipeline you keep.

None of that is done here — it's a real design decision, not a
missing-file fix, and picking for you risked breaking the one pipeline
that currently works without any way to verify it in this environment
(no `fastapi`/`xgboost`/`prophet` installed here to run the app or
retrain a model against real data).
