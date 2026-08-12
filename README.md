# 🌾 AgriGuard

> **Agricultural intelligence for Uganda** — crop price forecasting and
> counterfeit-input detection for smallholder farmers, delivered via a
> Streamlit dashboard and a USSD interface for feature phones.

Built by **Keith Ndiema Kissa** (2025/BCS/101/PS) · Mbarara University of
Science and Technology · Selected for Uganda's Ministry of ICT Government
Systems Prototype Showcase, June 2026.

---

## Status at a glance

| Layer | State |
|---|---|
| FastAPI backend — forecasts, markets, USSD | **Working.** Wired into `main.py`, backed by the committed WFP CSV. |
| Streamlit dashboard | **Working.** Reads from the backend over HTTP. |
| Price forecasting (XGBoost / Prophet) + counterfeit detection (Isolation Forest) | **Working**, trainable via `scripts/train_models.py`. |
| `prices` router (CRUD price observations, MySQL-backed) | **Not wired in.** See Known Issues. |
| Weather data collection | **Working as a standalone script**, not yet joined into the forecasting features. See `data/README.md`. |
| `quant/` package | **Scaffold only** — empty files, shared discipline with [Vestora](https://github.com/Ve-stora/vestora)'s quant module, not yet implemented. |
| `mobile/` (Flutter), `desktop/` (Tauri), `shared/api-client/` | **Scaffold only** — directory structure and dependency manifests exist; no implementation yet. |
| `fixed_files/` | **Legacy.** An earlier patch-delivery snapshot of a subset of files, now superseded by the real ones in `backend/`, `config/`, `scripts/`. Kept for reference; safe to delete once diffed. |

This section exists so the rest of the README doesn't have to hedge every
claim — anything described below as working, is working; anything listed
above as scaffold/legacy is described that way in its own section too.

## Problem

Ugandan farmers face three compounding challenges:

- **Price blindness** — no reliable way to know if today is a good day to sell
- **Counterfeit inputs** — fake seeds and pesticides cost farmers yield and money
- **Market fragmentation** — price gaps between markets go unexploited because farmers lack data

## Solution

| Module | What it does | How |
|---|---|---|
| **Price Forecasting** | Predicts crop prices weeks ahead, per market | XGBoost on WFP price history, Prophet as an alternative single-series forecaster |
| **Input Validator** | Flags suspicious agro-input reports | Isolation Forest anomaly detection, optional Claude Vision label scan |
| **Market Intelligence** | Cross-market comparisons, biggest movers, national summary | FastAPI serving the WFP dataset with trend analytics |

Accessible via a **Streamlit web dashboard** and a **USSD interface**
(`/ussd/simulate` locally; a real short-code requires an Africa's Talking
account — see `config/README.md`) for farmers without smartphones.

## Architecture

```
┌───────────────────────────────────────────────────────┐
│  Streamlit Frontend  (port 8501)                       │
│  Home · Dashboard · Price Forecast · Fake Detector      │
│  · USSD Simulator                                       │
└────────────────────┬─────────────────────────────────── ┘
                      │ HTTP / REST
┌────────────────────▼─────────────────────────────────── ┐
│  FastAPI Backend  (port 8000)                            │
│  /forecasts/*  /markets/*  /ussd/*                       │
│  /api/v1/predict  /api/v1/validate  /health               │
│  ( /prices/* implemented but not yet wired — see below ) │
└──────┬─────────────┬──────────────┬───────────────────── ┘
       │              │              │
  XGBoost         Prophet        SQLite (dev)
  + IsoForest     fallback       / MySQL (prod)
  .pkl in ml/models/
       │
  data/raw/wfp_food_prices_uga.csv  ←  scripts/download_wfp_data.py
```

## Quick Start

### 1. Clone and set up environment

```bash
git clone https://github.com/Agri-Guard/AgriGuard.git
cd AgriGuard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp config/.env.example config/.env
# edit config/.env — at minimum set ANTHROPIC_API_KEY if you want the
# Claude Vision fake-input check; everything else has a working dev default
```
See `config/README.md` for the full variable reference and how config
resolution/precedence works.

### 3. Get data and train models

```bash
python scripts/download_wfp_data.py      # writes data/raw/wfp_food_prices_uga.csv
python scripts/train_models.py           # trains XGBoost + Isolation Forest -> ml/models/
```
See `data/README.md` for the dataset schema, provenance, and what's
git-ignored vs. committed.

### 4a. Run with Docker Compose (recommended)

```bash
docker-compose up --build
```
- Dashboard: http://localhost:8501
- API docs:  http://localhost:8000/docs

To force fresh data + model training first: `docker-compose --profile train run --rm trainer`.

### 4b. Run natively, no Docker

```bash
./run.sh            # sets up venv, installs deps, copies config/.env, runs both services
./run.sh --setup    # also runs download_wfp_data.py + train_models.py first
```

### 4c. Run manually

```bash
# Terminal 1 — backend
uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && streamlit run Home.py --server.port 8501
```

## Project Structure

```
AgriGuard/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entry point + router wiring
│   │   ├── core/config.py     # Settings, reads config/.env — see config/README.md
│   │   ├── model.py           # ML model loader + inference (XGBoost, IsoForest)
│   │   ├── validator.py       # Input validation
│   │   ├── schemas.py         # Core Pydantic schemas
│   │   ├── routers/
│   │   │   ├── forecasts.py   # /forecasts/* — XGBoost/Prophet forecasts
│   │   │   ├── markets.py     # /markets/*   — market intelligence
│   │   │   ├── ussd.py        # /ussd/*      — USSD menu tree + simulator
│   │   │   └── prices.py      # /prices/*    — implemented, NOT wired into main.py
│   │   ├── models/, schemas/  # SQLAlchemy ORM + price-domain schemas (used by prices.py)
│   │   ├── database.py        # SQLAlchemy engine/session (used by prices.py)
│   │   └── services/          # price_service.py, forecast_service.py
│   └── ml/                    # importable package: config.py, features.py,
│                               # price_forecast_model.py, anomaly_detector.py, train.py
├── frontend/                  # Streamlit: Home.py + pages/{dashboard,price_forecast,
│                               # fake_detector,ussd_simulator}.py
├── ml/                        # training/evaluation workspace (not imported at runtime)
│   ├── training/               # train_price_model.py, train_anomaly_model.py, feature_engineering.py
│   ├── evaluation/              # evaluate_forecasts.py
│   ├── models/                 # trained .pkl artifacts (gitignored) + metrics.json (committed)
│   └── README.md                # backend/ml/ vs ml/ split, explained
├── quant/                      # SCAFFOLD — backtesting/intervals/risk-metrics, not yet implemented
├── mobile/                     # SCAFFOLD — Flutter app skeleton, not yet implemented
├── desktop/                    # SCAFFOLD — Tauri app skeleton, not yet implemented
├── shared/api-client/          # SCAFFOLD — shared TS API client, not yet implemented
├── scripts/
│   ├── download_wfp_data.py    # fetch WFP Uganda CSV from HDX
│   ├── fetch_weather.py        # fetch Open-Meteo weather (not yet joined into ML features)
│   ├── train_models.py         # train XGBoost + Isolation Forest
│   ├── load_data.py            # load prices into a DB (used by the not-yet-wired prices layer)
│   └── validate_data.py        # EMPTY STUB — see data/README.md "Data quality"
├── notebooks/                  # tiered forecasting validation pipeline, run 01→05 — see notebooks/README.md
├── tests/                      # test_api.py, test_models.py
├── data/                       # WFP prices + Open-Meteo weather — see data/README.md
├── config/                     # env templates — see config/README.md
├── fixed_files/                # LEGACY — superseded snapshot, see Known Issues
├── docs/                       # project documentation (Ministry of ICT showcase materials)
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## ML Methodology

### Price Forecasting (XGBoost)

**Features:** temporal (year, month, week, day-of-year, cyclic month
encoding), lag prices (1m, 3m, 6m), 3-month rolling average, label-encoded
crop and market.

**Training split:** 80/20 time-ordered (no data leakage).

**Metrics** (see `ml/models/metrics.json` after training — an append-only
run history, not a single snapshot):

| Metric | Value |
|---|---|
| MAE | ~120 UGX/kg |
| MAPE | ~8% |
| R² | ~0.91 |

Prophet is used as an alternative for single-series forecasting and as a
confidence-interval reference. `notebooks/` documents a more ambitious
tiered (7/14/30/60–90 day) backtested version of this pipeline that hasn't
been promoted into `scripts/train_models.py` yet — see `notebooks/README.md`.

### Counterfeit Detection (Isolation Forest)

Trained on the price feature space. Inputs that deviate significantly from
the training distribution are flagged as potentially anomalous.
`contamination=0.05` — a starting estimate, not a measured rate; retune once
real MAAIF field data on counterfeit incidence exists (see
`backend/ml/config.py`).

## API Reference

Full interactive docs at `/docs` when the backend is running.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | System health check |
| POST | `/api/v1/predict` | Quick price prediction |
| POST | `/api/v1/validate` | Fake input detector |
| GET | `/forecasts/{commodity}` | ML price forecast |
| GET | `/forecasts/commodities` | List available crops/markets |
| GET | `/forecasts/history/{commodity}` | Historical price series |
| GET | `/forecasts/compare/{commodity}` | Compare forecast approaches |
| GET | `/markets/summary/{commodity}` | Best/worst market for a commodity |
| GET | `/markets/overview/{market}` | All commodities at one market |
| GET | `/markets/movers` | Biggest price gainers/losers |
| GET | `/markets/arbitrage/{commodity}` | Cross-market arbitrage opportunities |
| GET | `/markets/national-summary` | All commodities, national snapshot |
| POST | `/ussd/`, `/ussd/simulate` | USSD session handler / local simulator (no Africa's Talking account needed) |

`/prices/*` (paginated CRUD over price observations) is implemented in
`backend/app/routers/prices.py` but not included in `main.py` — see Known
Issues before wiring it in.

## Data Sources

- **[WFP VAM Food Prices — Uganda](https://data.humdata.org/dataset/wfp-food-prices-for-uganda)** (HDX, open license) — historical crop prices, 10 markets, 8 commodities, 2018–present
- **[Open-Meteo](https://open-meteo.com)** — free daily weather + 16-day forecast, no API key required, currently 8 of 10 markets covered
- **Anthropic Claude Vision API** — optional counterfeit label scanning

Full schema, provenance, and refresh commands: `data/README.md`.

## Known Issues

Kept here instead of silently fixed, so anyone picking this up knows what's
real vs. aspirational:

- **`prices` router is implemented but not wired into `main.py`.** It depends
  on `database.py` / `services/price_service.py` / `models/price.py`, which
  assume a MySQL-backed deployment this `docker-compose.yml` doesn't provision
  a service for. `DATABASE_URL` falls back to SQLite for dev, which the
  `aiomysql` driver in `requirements.txt` doesn't target — reconcile before
  wiring this router in.
- **`scripts/validate_data.py` is an empty file.** No schema/range validation
  currently runs on either dataset before training. See `data/README.md`.
- **Weather data isn't joined into the forecasting features yet.** Collected
  by `scripts/fetch_weather.py`, documented in `data/README.md`, but no
  training or inference code reads it.
- **`quant/`, `mobile/`, `desktop/`, `shared/api-client/`** are directory
  scaffolds with dependency manifests but zero implementation — every file
  in them is currently empty.
- **`fixed_files/`** is a standalone snapshot from an earlier fix pass
  (its own `README.md`, `config/.env.example`, `backend/app/main.py`, etc.)
  that predates the current, real versions of those files elsewhere in the
  repo. It's not imported or referenced by anything and should be diffed
  against the current files and removed rather than kept as a silent second
  copy — that's exactly the kind of drift that caused the filename bugs
  fixed in this pass (see below).
- **Three filename mismatches in `ml/` fixed in this pass:**
  `backend/ml/config.py` and `ml/evaluation/evaluate_forecasts.py` pointed at
  a nonexistent `data/raw/wfp_uganda_prices.csv`; `ml/training/train_anomaly_model.py`
  had the same bug; `ml/training/train_price_model.py` pointed at a
  nonexistent `data/raw/uganda_food_prices.csv` and saved models to
  `ml/saved_models/` instead of `ml/models/`. All four now point at the one
  real file, `data/raw/wfp_food_prices_uga.csv`, and the one real artifact
  directory, `ml/models/`. See `data/README.md` §1 for the consumer list.
- **`config/env.example` vs `config/.env.example` mismatch fixed in this
  pass.** `run.sh` checked for the wrong filename (missing leading dot) and
  silently never auto-created `config/.env` on a fresh clone; `docker-compose.yml`'s
  header comment had the same typo. Both now reference the real file.

## Roadmap

- [ ] Wire the `prices` router in behind a real MySQL service, or drop it
- [ ] Implement `scripts/validate_data.py`
- [ ] Join weather data into the price-forecasting feature set
- [ ] SMS push alerts via Africa's Talking
- [ ] Satellite crop health integration (Sentinel-2)
- [ ] District-level food security index
- [ ] Implement `mobile/`, `desktop/`, `shared/api-client/` past scaffolding
- [ ] Multi-country expansion (Kenya, Tanzania)

## License

Dual-licensed: **AGPL-3.0** for open-source/non-commercial use — see
[LICENSE](LICENSE). A commercial license is available for closed-source
use — see [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).

## Author

**Keith Ndiema Kissa**
BSc Computer Science · Mbarara University of Science and Technology
[veritasndiema@gmail.com](mailto:veritasndiema@gmail.com) · GitHub: [Agri-Guard](https://github.com/Agri-Guard)