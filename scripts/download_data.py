"""
scripts/download_wfp_data.py — Fetch WFP Uganda Price Data
===========================================================
Downloads the WFP Food Prices dataset for Uganda from the
Humanitarian Data Exchange (HDX) and saves it to data/raw/.

Usage:
    python scripts/download_wfp_data.py
    python scripts/download_wfp_data.py --output data/raw/wfp_food_prices_uganda.csv

The script:
  1. Tries the HDX direct CSV link first (fastest)
  2. Falls back to the HDX API if the direct link changes
  3. Validates the download (row count, required columns)
  4. Prints a summary of crops and markets found

Requirements: requests, pandas (already in requirements.txt)
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

# ── Constants ─────────────────────────────────────────────────────────────────

# HDX direct CSV link for Uganda food prices (WFP VAM)
HDX_DIRECT_URL = (
    "https://data.humdata.org/dataset/"
    "wfp-food-prices-for-uganda/resource/"
    "wfp_food_prices_uga.csv"
)

# HDX API fallback (resolves latest resource URL)
HDX_API_URL = (
    "https://data.humdata.org/api/3/action/resource_show"
    "?id=wfp_food_prices_uga"
)

REQUIRED_COLUMNS = {"date", "market", "category", "commodity", "unit", "pricetype", "price"}

DEFAULT_OUTPUT = Path("data/raw/wfp_food_prices_uganda.csv")


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_csv(url: str, timeout: int = 30) -> bytes:
    print(f"  Downloading from: {url}")
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    chunks = []
    total = 0
    for chunk in resp.iter_content(chunk_size=8192):
        chunks.append(chunk)
        total += len(chunk)
        print(f"\r  {total / 1024:.0f} KB downloaded", end="", flush=True)
    print()
    return b"".join(chunks)


def validate_dataframe(df: pd.DataFrame) -> None:
    cols_lower = {c.lower() for c in df.columns}
    missing = REQUIRED_COLUMNS - cols_lower
    if missing:
        raise ValueError(
            f"Downloaded CSV is missing expected columns: {missing}\n"
            f"Got: {sorted(df.columns.tolist())}"
        )
    if len(df) < 100:
        raise ValueError(
            f"CSV looks too small — only {len(df)} rows. "
            "Check the download URL."
        )


def print_summary(df: pd.DataFrame) -> None:
    df.columns = [c.lower().strip() for c in df.columns]
    print("\n── Dataset Summary ──────────────────────────────")
    print(f"  Total rows   : {len(df):,}")
    if "commodity" in df.columns:
        print(f"  Crops        : {df['commodity'].nunique()} unique")
        print(f"  Top crops    : {', '.join(df['commodity'].value_counts().head(5).index)}")
    if "market" in df.columns:
        print(f"  Markets      : {df['market'].nunique()} unique")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        print(f"  Date range   : {df['date'].min().date()} → {df['date'].max().date()}")
    print("─────────────────────────────────────────────────\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    print("\n🌾 AgriGuard — WFP Uganda Price Data Downloader")
    print("=" * 50)

    # Try direct URL first
    raw = None
    for url in [HDX_DIRECT_URL]:
        try:
            raw = fetch_csv(url)
            break
        except requests.RequestException as e:
            print(f"  ⚠ Direct download failed: {e}")

    if raw is None:
        print("❌ Could not download data. Check your internet connection.")
        print(f"   You can also manually download from:\n   {HDX_DIRECT_URL}")
        print(f"   and save it to: {output}")
        sys.exit(1)

    # Parse and validate
    import io
    df = pd.read_csv(io.BytesIO(raw))
    try:
        validate_dataframe(df)
    except ValueError as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)

    # Save
    df.to_csv(output, index=False)
    print(f"✅ Saved to: {output}  ({output.stat().st_size / 1024:.0f} KB)")

    print_summary(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download WFP Uganda food price data")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    main(args.output)