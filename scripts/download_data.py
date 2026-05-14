import requests
import pandas as pd
from pathlib import Path

def download_wfp_uganda():
    """Download Uganda food price data from WFP VAM API."""
    url = "https://api.vam.wfp.org/economicExplorer/TradingCommodities"
    params = {
        "adm0Code": 181,  # Uganda country code
        "page": 1,
        "pageSize": 1000,
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    df = pd.DataFrame(data["items"])
    
    out = Path("data/raw/uganda_food_prices.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Saved {len(df)} records to {out}")

if __name__ == "__main__":
    download_wfp_uganda()