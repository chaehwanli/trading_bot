import pandas as pd
import json
import logging
from backtester.engine import prepare_dataset

logging.basicConfig(level=logging.INFO)

def main():
    # Load config for indicators
    with open("data_fetcher_config.json", "r") as f:
        config = json.load(f)
    
    ind_settings = config.get("indicators", {})
    symbol = "TSLA"
    interval = "1h"
    
    print(f"Verifying indicators for {symbol}...")
    file_path = f"data/{symbol}/{interval}.csv"
    try:
        # Check raw CSV columns
        df = pd.read_csv(file_path)
        print("CSV Columns:", df.columns.tolist())
        
        # Also usage of prepare_dataset to see if it loads correctly
        
        if 'rsi' in df.columns and 'macd' in df.columns:
            print("SUCCESS: RSI and MACD columns are present.")
            print("RSI Sample:", df['rsi'].tail(5).values)
            print("MACD Sample:", df['macd'].tail(5).values)
        else:
            print("FAILURE: Missing indicator columns.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
