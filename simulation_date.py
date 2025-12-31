
import sys
import os
from datetime import datetime, date, timedelta
import pytz

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tesla_reversal_trading_bot import TeslaReversalTradingBot
from config.holidays import KRX_HOLIDAYS

def simulate_calculation():
    # 1. Setup Bot (Mocking)
    bot = TeslaReversalTradingBot(is_paper_trading=True)
    
    # 2. Check Exchange for TSLS
    symbol = "TSLS"
    exchange = bot.kis._guess_exch_code(symbol)
    print(f"Symbol: {symbol}, Exchange: {exchange}")
    
    # 3. Simulate Date Calculation
    start_date = date(2025, 12, 30) # Tuesday
    target_days = 1 # SHORT
    
    # Use the bot's method logic (re-implemented here for clarity or call if possible)
    # Since we can't easily inject exchange into the bot instance without partial init, 
    # let's just use the logic directly.
    
    print(f"Start Date: {start_date}")
    
    current_date = start_date
    added_days = 0
    days = target_days
    
    # Logic from bot
    while added_days < days:
         current_date += timedelta(days=1)
         
         # 1. 주말 체크: 토(5), 일(6) 제외
         if current_date.weekday() >= 5:
             print(f"  Skipping Weekend: {current_date}")
             continue
             
         # 2. 휴장일 체크 (KRX인 경우)
         if exchange == "KRX" and current_date in KRX_HOLIDAYS:
             print(f"  Skipping KRX Holiday: {current_date}")
             continue
             
         print(f"  Adding Day: {current_date}")
         added_days += 1
         
    forced_close_date = current_date
    print(f"Forced Close Date: {forced_close_date}")
    
    # 4. Check against Current Time (User Scenario)
    # User Time: 2026-01-01 03:31:20 KST
    kst = pytz.timezone("Asia/Seoul")
    current_time_kst = kst.localize(datetime(2026, 1, 1, 3, 31, 20))
    
    market_timezone = pytz.timezone("US/Eastern") if exchange != "KRX" else kst
    current_market_time = current_time_kst.astimezone(market_timezone)
    current_market_date = current_market_time.date()
    
    print(f"Current KST: {current_time_kst}")
    print(f"Current Market Time ({market_timezone}): {current_market_time}")
    print(f"Current Market Date: {current_market_date}")
    
    should_close = current_market_date >= forced_close_date
    print(f"Should Close? {current_market_date} >= {forced_close_date} -> {should_close}")

if __name__ == "__main__":
    simulate_calculation()
