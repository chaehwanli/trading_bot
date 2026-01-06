from datetime import datetime, date
import pytz

def test_dates():
    market_timezone = pytz.timezone("US/Eastern")
    market_date = datetime.now(market_timezone).date()
    forced_close_date = date(2025, 12, 31)
    
    print(f"Current Market TZ: {market_timezone}")
    print(f"Market Date: {market_date} (Type: {type(market_date)})")
    print(f"Forced Close Date: {forced_close_date} (Type: {type(forced_close_date)})")
    
    if market_date >= forced_close_date:
        print("Condition [market_date >= forced_close_date] is TRUE")
    else:
        print("Condition [market_date >= forced_close_date] is FALSE")
        
    # Simulate string case just in case
    forced_close_date_str = "2025-12-31"
    try:
        if market_date >= forced_close_date_str:
            print("String Comparison: TRUE")
        else:
             print("String Comparison: FALSE")
    except Exception as e:
        print(f"String Comparison Error: {e}")

import schedule
import time

def job_with_error():
    print("Executing job...")
    d = date(2026, 1, 6)
    s = "2025-12-31"
    if d >= s:
        print("Comparison success")
    print("Job finished")

def test_schedule():
    print("\nTesting Schedule Exception Handling...")
    schedule.every(1).seconds.do(job_with_error)
    
    try:
        schedule.run_pending()
        time.sleep(1.1)
        schedule.run_pending()
    except Exception as e:
        print(f"Schedule Exception Caught: {e}")
    else:
        print("Schedule executed without catching main exception (it might have crashed inside job?)")

if __name__ == "__main__":
    test_dates()
    test_schedule()
