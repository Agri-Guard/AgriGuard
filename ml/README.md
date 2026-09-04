# ml/

**Last verified against the repo Sep 2026.**

This directory used to describe four separate, competing price-forecasting
implementations. Three of them were never loaded by anything live and have
been moved to `archive/deprecated-ml-pipelines/` (see that folder's README
for the full history and why).

## What's here now

**`scripts/train_models.py` is the only training pipeline, and it's the one
the FastAPI backend actually uses.** It writes
`ml/models/price_forecast_model.pkl` + `ml/models/encoders.pkl`, and
`backend/app/model.py` loads exactly those two files by name at request
time.

```bash
# from repo root, after scripts/download_wfp_data.py has produced
# data/raw/wfp_food_prices_uga.csv
python scripts/train_models.py
```

This feeds the **point-prediction** endpoint in `backend/app/model.py` —
a single price estimate for a given crop×market.

It is a *separate* thing from the **multi-day forecast curve** served by
`backend/app/routers/forecasts.py` (`/forecasts/{commodity}`, `/forecasts/
compare/...`), which fits Prophet (or a linear-extrapolation fallback) per
request rather than loading a saved model — see that router's docstring.
Neither of these two live paths currently reads anything produced by
`quant/`.

## `quant/`

`quant/` (walk-forward backtesting, prediction intervals, per-series risk
scoring, Prophet-vs-XGBoost model selection) is a separate, newer layer —
see `quant/README.md`. It has its own production feature-generation step
(`scripts/build_quant_features.py`) and its own tests
(`quant/tests/`), and does not depend on anything in this directory.
It is **not yet consulted by either live forecasting path above** — that's
the next integration step, not something this cleanup did.

## `ml/models/`

Where `scripts/train_models.py` writes its two `.pkl` files and
`metrics.json`. Kept empty in git (`.gitkeep`) since trained artifacts
aren't committed.
