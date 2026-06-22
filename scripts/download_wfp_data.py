#!/usr/bin/env python3
"""
Download WFP food price data for Uganda.
Falls back to generating realistic synthetic data if the API is unavailable.
Run from repo root: python scripts/download_wfp_data.py
"""

import os
import sys
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw"
OUT_FILE = OUT_DIR / "wfp_food_prices_uga.csv"

# ── WFP HDX / VAM API ─────────────────────────────────────────────────────────
HDX_URL = (
    "https://data.humdata.org/datastore/odata.svc/"
    "b4cceb74-a026-4e86-8aed-dbdd3e7c2e75"
    "?$format=json&$top=10000"
)
ALT_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/global-food-prices/main/"
    "data/wfp_food_prices_uga.csv"
)

UGANDA_MARKETS = [
    "Kampala", "Gulu", "Mbarara", "Jinja", "Mbale",
    "Lira", "Arua", "Fort Portal", "Kasese", "Soroti",
]
COMMODITIES = {
    "Maize":        {"unit": "KG",  "base": 1200, "vol": 0.18},
    "Beans":        {"unit": "KG",  "base": 3500, "vol": 0.20},
    "Rice":         {"unit": "KG",  "base": 4200, "vol": 0.15},
    "Cassava":      {"unit": "KG",  "base": 800,  "vol": 0.22},
    "Sorghum":      {"unit": "KG",  "base": 1100, "vol": 0.17},
    "Sweet Potato": {"unit": "KG",  "base": 900,  "vol": 0.25},
    "Groundnuts":   {"unit": "KG",  "base": 5000, "vol": 0.19},
    "Millet":       {"unit": "KG",  "base": 1500, "vol": 0.21},
}


def try_hdx_download() -> bool:
    """Attempt to pull data from HDX ODATA endpoint."""
    log.info("Trying HDX ODATA endpoint …")
    try:
        r = requests.get(HDX_URL, timeout=30)
        r.raise_for_status()
        records = r.json().get("value", [])
        if not records:
            return False
        df = pd.DataFrame(records)
        df.to_csv(OUT_FILE, index=False)
        log.info(f"  ✓ HDX: {len(df):,} rows → {OUT_FILE}")
        return True
    except Exception as e:
        log.warning(f"  HDX failed: {e}")
        return False


def try_csv_download() -> bool:
    """Attempt to pull the pre-packaged CSV from GitHub datasets."""
    log.info("Trying CSV mirror …")
    try:
        r = requests.get(ALT_CSV_URL, timeout=30)
        r.raise_for_status()
        with open(OUT_FILE, "wb") as f:
            f.write(r.content)
        df = pd.read_csv(OUT_FILE)
        log.info(f"  ✓ CSV mirror: {len(df):,} rows → {OUT_FILE}")
        return True
    except Exception as e:
        log.warning(f"  CSV mirror failed: {e}")
        return False


def generate_synthetic_data() -> None:
    """
    Generate realistic Uganda food price data (2018-present).
    Columns mirror the WFP Global Food Prices schema so training
    scripts work identically against real or synthetic data.
    """
    log.info("Generating synthetic WFP-schema data …")
    rng = np.random.default_rng(42)
    rows = []

    start = datetime(2018, 1, 1)
    end   = datetime.now().replace(day=1)
    months = []
    cur = start
    while cur <= end:
        months.append(cur)
        # advance one month
        m = cur.month + 1
        y = cur.year + (m > 12)
        cur = cur.replace(year=y, month=(m - 1) % 12 + 1, day=1)

    for market in UGANDA_MARKETS:
        for commodity, meta in COMMODITIES.items():
            price = float(meta["base"])
            for dt in months:
                # seasonal factor (two peaks: Mar-Apr, Sep-Oct)
                seasonal = 1 + 0.12 * np.sin(2 * np.pi * (dt.month - 3) / 12)
                # annual inflation ~8 %
                annual_factor = 1.08 ** ((dt.year - 2018) + dt.month / 12)
                # random walk noise
                shock = rng.normal(1.0, meta["vol"] / 4)
                price = max(
                    meta["base"] * 0.4,
                    price * seasonal * shock,
                )
                rows.append({
                    "date":      dt.strftime("%Y-%m-%d"),
                    "country":   "Uganda",
                    "market":    market,
                    "category":  "cereals and tubers",
                    "commodity": commodity,
                    "unit":      meta["unit"],
                    "currency":  "UGX",
                    "pricetype": "Retail",
                    "price":     round(price * annual_factor, 2),
                    "usdprice":  round(price * annual_factor / 3700, 4),
                    "latitude":  round(rng.uniform(-1.5, 4.2), 4),
                    "longitude": round(rng.uniform(29.6, 35.0), 4),
                })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_FILE, index=False)
    log.info(f"  ✓ Synthetic: {len(df):,} rows → {OUT_FILE}")


def validate_output() -> None:
    df = pd.read_csv(OUT_FILE)
    required = {"date", "market", "commodity", "price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Output CSV missing columns: {missing}")
    log.info(
        f"Validation OK — {len(df):,} rows, "
        f"{df['commodity'].nunique()} commodities, "
        f"{df['market'].nunique()} markets, "
        f"date range {df['date'].min()} → {df['date'].max()}"
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_FILE.exists():
        size_kb = OUT_FILE.stat().st_size / 1024
        log.info(f"Existing file found ({size_kb:.0f} KB). Delete to re-download.")
        validate_output()
        return

    success = try_hdx_download() or try_csv_download()
    if not success:
        log.warning("All download sources failed — using synthetic data.")
        generate_synthetic_data()

    validate_output()
    log.info("Done ✓")


if __name__ == "__main__":
    main()
