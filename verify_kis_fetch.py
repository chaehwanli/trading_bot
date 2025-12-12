from data.data_fetcher import DataFetcher
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

def test_fetch_data():
    fetcher = DataFetcher()
    symbol = "TSLT"
    
    print(f"Testing Realtime Price for {symbol}...")
    price = fetcher.get_realtime_price(symbol)
    print(f"Realtime Price: {price}")
    
    print(f"\nTesting Historical Data (Daily) for {symbol}...")
    daily_data = fetcher.get_historical_data(symbol, period="1h", interval="max")
    if daily_data is not None:
        print(daily_data.head())
        print(daily_data.tail())
    else:
        print("Daily data fetch failed.")

    print(f"\nTesting Historical Data (Hourly) for {symbol}...")
    # NOTE: KIS API implementation for "1h" maps to minute chart with hardcoded parameters in kis_api.py
    hourly_data = fetcher.get_historical_data(symbol, period="1h", interval="max")
    if hourly_data is not None:
        print(hourly_data.head())
        print(hourly_data.tail())
    else:
        print("Hourly data fetch failed.")

if __name__ == "__main__":
    test_fetch_data()
