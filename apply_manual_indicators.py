import json
import logging
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from run_data_fetcher import load_config
from backtester.engine import prepare_dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    config = load_config()
    ind_settings = config.get("indicators", {})
    symbol = "TSLA"
    interval = "1h"
    
    print(f"Applying indicators for {symbol}...")
    try:
        # prepare_dataset loads CSV, calculates indicators, dedupes
        df = prepare_dataset(symbol, interval, tz=None, ind_params=ind_settings)
        
        save_path = f"data/{symbol}/{interval}.csv"
        df.to_csv(save_path)
        print(f"Saved {symbol} with indicators to {save_path}. Columns: {df.columns.tolist()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
