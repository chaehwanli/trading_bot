from trading.kis_api import KisApi
from utils.logger import logger
import sys

def test_us_api():
    print("Testing US API Functionality...")
    kis = KisApi(is_paper_trading=True) # Use paper trading for safety
    
    symbol = "TSLA"
    
    # Test 1: Daily Price
    print(f"\n1. Testing get_daily_price({symbol})...")
    daily_data = kis.get_daily_price(symbol)
    if daily_data and len(daily_data) > 0:
        print(f"✅ Success: Retrieved {len(daily_data)} daily records.")
        print(f"   Sample: {daily_data[0]}")
    else:
        print("❌ Failed to retrieve daily price.")
        
    # Test 2: Minute Price
    print(f"\n2. Testing get_minute_price({symbol})...")
    minute_data = kis.get_minute_price(symbol)
    if minute_data and len(minute_data) > 0:
        print(f"✅ Success: Retrieved {len(minute_data)} minute records.")
        print(f"   Sample: {minute_data[0]}")
    else:
        print("❌ Failed to retrieve minute price.")

if __name__ == "__main__":
    test_us_api()
