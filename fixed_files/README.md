# 🌾 AgriGuard

> **Agricultural Intelligence System for Uganda** — crop price forecasting, counterfeit input detection, and market intelligence delivered to farmers via web dashboard and USSD.

Built by **Keith Ndiema Kissa** (2025/BCS/101/PS) · Mbarara University of Science and Technology  
Submitted: Ministry of ICT Government Systems Prototype Showcase 2026 ·



## Problem

Ugandan farmers face three compounding challenges:

- **Price blindness** — no reliable way to know if today is a good day to sell
- **Counterfeit inputs** — fake seeds and pesticides cost farmers yield and money
- **Market fragmentation** — price gaps between markets go unexploited because farmers lack data

## Solution

AgriGuard is a three-module intelligence layer:

| Module | What it does | How |
|---|---|---|
| **Price Forecasting** | Predicts crop prices 4 weeks ahead | XGBoost + Prophet on WFP price history |
| **Input Validator** | Flags suspicious agro-input reports | Isolation Forest anomaly detection + Claude Vision label scanner |
| **Market Intelligence** | Cross-market comparisons, arbitrage signals | FastAPI serving WFP data with trend analytics |

Accessible via a **Streamlit web dashboard** and a **USSD interface** (`*183*7#`) for farmers without smartphones.



## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Streamlit Frontend  (port 8501)                    │
│  Home · Dashboard · USSD Simulator                  │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼────────────────────────────────┐
│  FastAPI Backend  (port 8000)                       │
│  /forecasts  /markets  /prices  /api/v1/predict     │
│  /api/v1/validate  /health                          │
└──────┬─────────────┬──────────────┬─────────────────┘
       │             │              │
  XGBoost        Prophet        MySQL DB
  + IsoForest    fallback       (price history)
  .pkl models    (no model)
       │
  WFP Uganda CSV  ←  scripts/download_wfp_data.py
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
# Edit config/.env — set ANTHROPIC_API_KEY if you want the (not-yet-wired) vision scanner
```

### 3. Download data and train models

```bash
python scripts/download_wfp_data.py      # ~2 MB WFP Uganda CSV
python scripts/train_models.py           # trains XGBoost + Isolation Forest
```

### 4a. Run with Docker Compose (recommended)

```bash
docker-compose up --build
```

- Dashboard: http://localhost:8501
- API docs:  http://localhost:8000/docs

### 4b. Run manually

```bash
# Terminal 1 — backend
uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
streamlit run Home.py --server.port 8501
```



## Project Structure

```
AgriGuard/
├── backend/
│   ├── Dockerfile
│   └── app/
│       ├── main.py           # FastAPI entry point + router wiring
│       ├── core/config.py    # Settings (env-var driven, dotenv fallback) — the live one
│       ├── model.py          # ML model loader + inference
│       ├── validator.py      # Input validation
│       ├── schemas.py        # Core Pydantic schemas
│       ├── routers/
│       │   ├── forecasts.py  # Prophet/XGBoost forecast endpoints — wired
│       │   ├── markets.py    # Market intelligence endpoints — wired
│       │   ├── ussd.py       # Feature-phone USSD menu — wired
│       │   └── prices.py     # CRUD price endpoints — NOT wired yet, see Known issues
│       ├── database.py       # SQLAlchemy engine — WIP, not used by anything wired in
│       ├── models/price.py   # SQLAlchemy ORM — WIP, same as above
│       ├── schemas/price.py  # Price-domain schemas for prices.py — WIP, same as above
│       └── services/price_service.py  # WIP, same as above
├── frontend/
│   ├── Dockerfile
│   ├── Home.py               # Landing page
│   └── pages/
│       ├── dashboard.py      # Main 5-tab dashboard
│       └── ussd_simulator.py # Feature-phone USSD demo
├── scripts/
│   ├── download_wfp_data.py  # Fetch WFP Uganda CSV from HDX
│   └── train_models.py       # Train XGBoost + Isolation Forest
├── ml/
│   └── models/               # Saved .pkl files (gitignored)
│       └── metrics.json      # Evaluation metrics (committed)
├── data/
│   └── raw/                  # WFP CSV (gitignored)
├── config/
│   └── env.example           # Copy to .env and fill in
├── docker-compose.yml
├── requirements.txt
└── README.md
```



## ML Methodology

### Price Forecasting (XGBoost)

**Features:** temporal (year, month, week, day-of-year, cyclic month encoding), lag prices (1m, 3m, 6m), 3-month rolling average, label-encoded crop and market.

**Training split:** 80/20 time-ordered (no data leakage).

**Metrics** (see `ml/models/metrics.json` after training):

| Metric | Value |
|---|---|
| MAE | ~120 UGX/kg |
| MAPE | ~8% |
| R² | ~0.91 |

Prophet is used as an alternative for single-series forecasting and as a confidence-interval reference.

### Counterfeit Detection (Isolation Forest)

Trained on the price feature space. Inputs that deviate significantly from the training distribution are flagged as potentially anomalous. `contamination=0.05` (tunable based on field error rate estimates from MAAIF).



## API Reference

Full interactive docs at `/docs` when the backend is running.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | System health check |
| POST | `/api/v1/predict` | Quick price prediction |
| POST | `/api/v1/validate` | Fake input detector |
| GET | `/forecasts/{commodity}` | ML price forecast |
| GET | `/forecasts/commodities` | List available crops/markets |
| GET | `/markets/summary/{commodity}` | Best/worst market |
| GET | `/markets/movers` | Biggest price gainers/losers |
| GET | `/markets/national-summary` | All commodities snapshot |
| POST | `/ussd/` | Africa's Talking USSD webhook |
| GET | `/ussd/simulate` | Simulate a USSD session in a browser/curl, no gateway needed |

`/prices` and `/prices/alerts` exist in `routers/prices.py` but aren't mounted yet — see **Known issues** below. `/api/v1/validate` currently returns `501` — the fake-input schema doesn't carry the physical measurements the model needs; see the same section.



## Data Sources

- **[WFP VAM Food Prices — Uganda](https://data.humdata.org/dataset/wfp-food-prices-for-uganda)** (HDX, open license) — historical crop prices across Ugandan markets
- **[Open-Meteo](https://open-meteo.com)** — free 7-day weather forecasts (no API key required)
- **Anthropic Claude Vision API** — counterfeit label scanning



## Known issues

- **`ml/models/*.pkl` are placeholders, not trained models.** Run `python scripts/train_models.py` after `download_wfp_data.py` to generate real `price_forecast_model.pkl`, `fake_detector_model.pkl`, and `encoders.pkl` before expecting `/api/v1/predict` or `/api/v1/validate` to return real predictions — right now the app boots and returns `503 Model not ready` for both.
- **`/api/v1/validate` returns `501`.** `FakeInputRequest` only carries `crop/region/date`, but the fake-detector model needs physical input-quality measurements (moisture %, purity %, germination rate, etc.) that aren't yet defined anywhere. This needs a schema decision once the training pipeline settles on its feature list.
- **`routers/prices.py` isn't mounted.** It depends on `database.py`, `models/price.py`, and `services/price_service.py`, which import a nonexistent top-level `app` package (should be `backend.app`) and assume a Postgres service that doesn't exist in `docker-compose.yml`. This whole layer needs a pass before it can be wired into `main.py`.
- **`/api/v1/predict` takes `{crop, region, date}`** and internally converts to the `{commodity, market, year, month}` shape `model.py` actually uses. `tests/test_api.py` was written against the `{commodity, market, year, month}` shape directly — worth deciding which is the real public contract and aligning the other side, rather than maintaining both.

## Roadmap

- [ ] SMS push alerts via Africa's Talking
- [ ] Satellite crop health integration (Sentinel-2)
- [ ] District-level food security index
- [ ] Mobile app (React Native)
- [ ] Multi-country expansion (Kenya, Tanzania)



## License

AGPL-3.0 — see [LICENSE](LICENSE)



## Author

**Keith Ndiema Kissa**  
BSc Computer Science · Mbarara University of Science and Technology  
[veritasndiema@gmail.com](mailto:veritasndiema@gmail.com) · GitHub: [Ve-stora](https://github.com/Ve-stora)