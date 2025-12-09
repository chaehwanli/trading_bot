
import sys
import os
import shutil
import pandas as pd
from datetime import datetime, timedelta

# Project root setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_fetcher import DataFetcher
from database.db_manager import DatabaseManager
from utils.logger import logger

def test_db_caching():
    # 0. Clean up existing DB for testing
    db_path = "trading_bot.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Existing DB removed.")

    fetcher = DataFetcher()
    symbol = "TSLA"
    period = "5d"
    interval = "1h"

    print(f"\n[Test 1] Fetching {symbol} (Expected: API Download + DB Save)")
    df1 = fetcher.get_historical_data(symbol, period=period, interval=interval)
    
    if df1 is None or df1.empty:
        print("FAILED: No data returned from API.")
        return

    print(f"Data fetched: {len(df1)} rows.")
    
    # Check if DB file created
    if not os.path.exists(db_path):
        print("FAILED: DB file not created.")
        return
    else:
        print("SUCCESS: DB file created.")

    # Verify data in DB
    db_manager = DatabaseManager()
    saved_data = db_manager.get_historical_data(symbol, interval, datetime.now() - timedelta(days=7), datetime.now())
    if saved_data is None or saved_data.empty:
        print("FAILED: Data not found in DB.")
    else:
        print(f"SUCCESS: Data found in DB ({len(saved_data)} rows).")

    print(f"\n[Test 2] Fetching {symbol} again (Expected: DB Load)")
    # We can check logs visually or trust the return value is same
    df2 = fetcher.get_historical_data(symbol, period=period, interval=interval)
    
    if df2 is None or df2.empty:
        print("FAILED: No data returned from DB.")
        return
        
    if len(df1) == len(df2):
        print(f"SUCCESS: Data length matches ({len(df2)} rows).")
    else:
        print(f"WARNING: Data length mismatch (API: {len(df1)}, DB: {len(df2)}). This might happen if new data arrived or time window shifted slightly.")

if __name__ == "__main__":
    test_db_caching()
