"""
scripts/train_models.py — AgriGuard ML Model Training Pipeline
===============================================================
Trains and saves two models:
  1. price_forecast_model.pkl  — XGBoost regressor for crop price prediction
  2. fake_detector_model.pkl   — Isolation Forest for anomaly / fake input detection

Usage:
    python scripts/train_models.py
    python scripts/train_models.py --data data/raw/wfp_food_prices_uganda.csv
    python scripts/train_models.py --data data/raw/wfp_food_prices_uganda.csv --out ml/models

Pipeline:
    load CSV → clean → feature engineering → train → evaluate → save

Evaluation metrics are printed to stdout and saved to ml/models/metrics.json.
These metrics are what you'll cite in your EPFL project write-up.
"""

import argparse
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

DEFAULT_DATA  = Path("data/raw/wfp_food_prices_uganda.csv")
DEFAULT_OUTDIR = Path("ml/models")


# =============================================================================
# 1. DATA LOADING & CLEANING
# =============================================================================

def load_and_clean(data_path: Path) -> pd.DataFrame:
    print(f"\n📂 Loading data: {data_path}")
    df = pd.read_csv(data_path)
    df.columns = [c.lower().strip() for c in df.columns]

    print(f"   Raw rows: {len(df):,}")

    # Normalise column names (WFP CSV uses slightly different names across years)
    rename_map = {
        "cmname":    "commodity",
        "mktname":   "market",
        "admname":   "region",
        "adm1name":  "region",
        "ptname":    "pricetype",
        "um":        "unit",
        "mp_price":  "price",
    }
    df.rename(columns=rename_map, inplace=True)

    # Keep only retail prices (most consistent signal for farmers)
    if "pricetype" in df.columns:
        df = df[df["pricetype"].str.lower().str.contains("retail", na=False)]

    # Parse date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "price", "commodity", "market"])

    # Numeric price
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df[df["price"] > 0]

    # Remove extreme outliers (> 5 std dev per commodity)
    def remove_outliers(group):
        mean, std = group["price"].mean(), group["price"].std()
        return group[np.abs(group["price"] - mean) <= 5 * std] if std > 0 else group

    df = df.groupby("commodity", group_keys=False).apply(remove_outliers)
    df = df.reset_index(drop=True)

    print(f"   Clean rows: {len(df):,}")
    print(f"   Crops     : {df['commodity'].nunique()}")
    print(f"   Markets   : {df['market'].nunique()}")
    print(f"   Date range: {df['date'].min().date()} → {df['date'].max().date()}")
    return df


# =============================================================================
# 2. FEATURE ENGINEERING
# =============================================================================

def build_features(df: pd.DataFrame):
    """
    Time-series features for XGBoost.
    All features are numeric — XGBoost doesn't need one-hot encoding,
    but label encoding gives it ordinal signal for crop/market.
    """
    df = df.copy()

    # Temporal features
    df["year"]        = df["date"].dt.year
    df["month"]       = df["date"].dt.month
    df["quarter"]     = df["date"].dt.quarter
    df["week"]        = df["date"].dt.isocalendar().week.astype(int)
    df["day_of_year"] = df["date"].dt.dayofyear

    # Cyclic encoding of month (captures seasonality smoothly)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # Lag features (previous observed price for same crop×market)
    df = df.sort_values(["commodity", "market", "date"])
    df["price_lag_1m"] = df.groupby(["commodity", "market"])["price"].shift(1)
    df["price_lag_3m"] = df.groupby(["commodity", "market"])["price"].shift(3)
    df["price_lag_6m"] = df.groupby(["commodity", "market"])["price"].shift(6)

    # Rolling statistics (3-month window)
    roll = df.groupby(["commodity", "market"])["price"].transform(
        lambda x: x.rolling(3, min_periods=1).mean()
    )
    df["price_roll_3m_avg"] = roll

    # Label-encode categorical columns
    le_crop   = LabelEncoder()
    le_market = LabelEncoder()
    df["crop_enc"]   = le_crop.fit_transform(df["commodity"].astype(str))
    df["market_enc"] = le_market.fit_transform(df["market"].astype(str))

    # Drop rows where lag features are NaN (first observations per group)
    feature_cols = [
        "crop_enc", "market_enc",
        "year", "month", "quarter", "week", "day_of_year",
        "month_sin", "month_cos",
        "price_lag_1m", "price_lag_3m", "price_lag_6m",
        "price_roll_3m_avg",
    ]
    df = df.dropna(subset=feature_cols)

    X = df[feature_cols]
    y = df["price"]

    return X, y, le_crop, le_market, feature_cols


# =============================================================================
# 3. TRAIN PRICE FORECAST MODEL (XGBoost)
# =============================================================================

def train_price_model(X, y):
    print("\n🤖 Training XGBoost price forecast model…")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False  # time-ordered split
    )

    model = XGBRegressor(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    preds = model.predict(X_test)

    mae  = mean_absolute_error(y_test, preds)
    rmse = mean_squared_error(y_test, preds) ** 0.5
    r2   = r2_score(y_test, preds)
    mape = np.mean(np.abs((y_test - preds) / y_test.clip(lower=1))) * 100

    print(f"   MAE  : {mae:,.2f} UGX")
    print(f"   RMSE : {rmse:,.2f} UGX")
    print(f"   MAPE : {mape:.2f}%")
    print(f"   R²   : {r2:.4f}")

    metrics = {
        "model":      "XGBoostRegressor",
        "n_train":    int(len(X_train)),
        "n_test":     int(len(X_test)),
        "MAE_UGX":    round(mae, 2),
        "RMSE_UGX":   round(rmse, 2),
        "MAPE_pct":   round(mape, 2),
        "R2":         round(r2, 4),
    }
    return model, metrics


# =============================================================================
# 4. TRAIN FAKE INPUT DETECTOR (Isolation Forest)
# =============================================================================

def train_fake_detector(X):
    """
    Isolation Forest trained on the price feature space.
    Inputs that are far from the training distribution are flagged
    as potential fake / erroneous reports.
    contamination=0.05 means ~5% of training data is treated as anomalous
    (tunable based on MAAIF field survey error rates).
    """
    print("\n🔍 Training Isolation Forest anomaly detector…")

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X)

    # Quick self-eval: fraction flagged on training data
    scores  = model.decision_function(X)
    flagged = (model.predict(X) == -1).sum()
    print(f"   Training samples : {len(X):,}")
    print(f"   Flagged as anomaly: {flagged:,} ({100*flagged/len(X):.1f}%)")
    print(f"   Score range      : [{scores.min():.3f}, {scores.max():.3f}]")

    metrics = {
        "model":             "IsolationForest",
        "n_train":           int(len(X)),
        "contamination":     0.05,
        "flagged_train_pct": round(100 * flagged / len(X), 1),
    }
    return model, metrics


# =============================================================================
# 5. SAVE ARTIFACTS
# =============================================================================

def save_artifacts(outdir: Path, price_model, fake_model, le_crop, le_market,
                   feature_cols, price_metrics, fake_metrics):
    outdir.mkdir(parents=True, exist_ok=True)

    price_path = outdir / "price_forecast_model.pkl"
    fake_path  = outdir / "fake_detector_model.pkl"
    meta_path  = outdir / "metrics.json"

    joblib.dump(price_model, price_path, compress=3)
    joblib.dump(fake_model,  fake_path,  compress=3)

    # Save encoders and feature list alongside models
    joblib.dump({"le_crop": le_crop, "le_market": le_market,
                 "feature_cols": feature_cols},
                outdir / "encoders.pkl", compress=3)

    all_metrics = {
        "price_forecast": price_metrics,
        "fake_detector":  fake_metrics,
    }
    with open(meta_path, "w") as f:
        json.dump(all_metrics, f, indent=2)

    print(f"\n✅ Saved:")
    print(f"   {price_path}  ({price_path.stat().st_size / 1024:.0f} KB)")
    print(f"   {fake_path}   ({fake_path.stat().st_size  / 1024:.0f} KB)")
    print(f"   {meta_path}")


# =============================================================================
# MAIN
# =============================================================================

def main(data_path: Path, outdir: Path):
    print("=" * 55)
    print("  AgriGuard — ML Model Training Pipeline")
    print("=" * 55)

    if not data_path.exists():
        print(f"\n❌ Data file not found: {data_path}")
        print("   Run first:  python scripts/download_wfp_data.py")
        raise SystemExit(1)

    df = load_and_clean(data_path)
    X, y, le_crop, le_market, feature_cols = build_features(df)

    price_model, price_metrics = train_price_model(X, y)
    fake_model,  fake_metrics  = train_fake_detector(X)

    save_artifacts(
        outdir, price_model, fake_model,
        le_crop, le_market, feature_cols,
        price_metrics, fake_metrics,
    )

    print("\n🎉 Training complete. Models ready for inference.")
    print(f"   MAPE: {price_metrics['MAPE_pct']}%  |  R²: {price_metrics['R2']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AgriGuard ML models")
    parser.add_argument("--data", "-d", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out",  "-o", type=Path, default=DEFAULT_OUTDIR)
    args = parser.parse_args()
    main(args.data, args.out)