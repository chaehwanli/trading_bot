import sys
import os
import time
import math

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading.kis_api import KisApi
from utils.logger import logger
import logging

def test_order_logic():
    # Configure logger to show DEBUG level on console for this test script
    # We must target the specific logger "trading_bot" used in kis_api.py
    tb_logger = logging.getLogger("trading_bot")
    tb_logger.setLevel(logging.DEBUG)
    
    for handler in tb_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
             handler.setLevel(logging.DEBUG)
    
    print("==================================================")
    print("      KIS API Real Account Order Test Logic       ")
    print("==================================================")

    # 1. Initialize API (Real Trading)
    # NOTE: Set is_paper_trading=False for REAL ACCOUNT testing
    print("\n[1] Initializing KIS API (Real Trading)...")
    kis = KisApi(is_paper_trading=False)
    
    # Try to ensure we have a valid token
    try:
        kis.ensure_valid_token()
    except Exception as e:
        print(f"❌ Error during token validation: {e}")
    
    if not kis.access_token:
        print("❌ Failed to get Access Token.")
        print("💡 Possible causes:")
        print("   1. Invalid KIS_API_KEY or KIS_API_SECRET in .env")
        print("   2. Your IP might not be registered in KIS Developer Portal")
        print("   3. Your OpenAPI service might be expired or not applied for Real Trading")
        print("   4. You might be using Paper Trading keys with the Real URL (or vice-versa)")
        return

    print("✅ API Initialized & Token Retrieved.")

    # 2. Check Balance
    print("\n[2] Checking Account Balance...")
    # Now get_balance() internally uses the dedicated 'inquire-deposit' API (TTTS3016R)
    deposit_usd = kis.get_balance()
    
    print(f"💰 Current USD Deposit (Available for Order): ${deposit_usd:,.2f}")

    if deposit_usd == 0:
        print("\n⚠️  Balance is 0. Debugging Asset Info...")
        # Fallback to verify what assets ARE there
        balance_data = kis.get_overseas_stock_balance()
        if balance_data and 'assets' in balance_data:
            print("   [Asset Dump] Here is what KIS API returned for your account:")
            assets = balance_data['assets']
            for k, v in assets.items():
                # Print only relevant fields or non-zero values to filter noise if wanted, 
                # but printing all is safer for debugging.
                print(f"   - {k}: {v}")
        else:
            print("   ❌ Failed to fetch asset dump as well.")
        
        trades_data = kis.get_overseas_trades()
        if trades_data and 'output' in trades_data:
            print("   [Trades Dump] Here is what KIS API returned for your account:")
            for trade in trades_data['output']:
                print(f"   - 종목코드: {trade.get('ovrs_pdno')}")
                print(f"     체결구분: {trade.get('ord_dvsn_name')}")
                print(f"     체결수량: {trade.get('ovrs_ccld_qty')}")
                print(f"     체결금액: {trade.get('frcr_ccld_amt')}")
                print("")
        else:
            print("   ❌ No trade data available (output not found).")

    # 3. Target Symbol for Test
    symbol = "TSLS" # Using TSLS (usually cheaper than TSLA) or TSLA
    print(f"\n[3] fetching Current Price for {symbol}...")
    
    current_price = kis.get_current_price(symbol)
    if not current_price:
        print(f"❌ Failed to fetch price for {symbol}")
        return

    print(f"📈 Current Price of {symbol}: ${current_price}")

    # 4. Prepare Safe Test Order
    # Strategy: Place a LIMIT BUY order at 50% of current price.
    # This ensures it will NOT executed immediately (unless market crashes 50% in 1 second).
    
    safe_price = round(current_price * 0.5, 2)
    qty = 1
    
    print("\n[4] Preparing Safe Test Order...")
    print(f"   Target: {symbol}")
    print(f"   Type: LIMIT BUY (00)")
    print(f"   Qty: {qty}")
    print(f"   Current Price: ${current_price}")
    print(f"   Order Price (50%): ${safe_price}  <-- SAFE MARGIN")
    
    estimated_cost = safe_price * qty
    print(f"   Estimated Cost: ${estimated_cost}")

    if deposit_usd < estimated_cost:
        print(f"❌ Insufficient Funds! You need at least ${estimated_cost} but have ${deposit_usd}")
        return

    confirm = input(f"\n⚠️  WARNING: You are about to place a REAL ORDER on your REAL ACCOUNT.\n"
                    f"    It is a LIMIT order at ${safe_price} (Current: ${current_price}).\n"
                    f"    It should NOT fill, but it WILL assume margin.\n"
                    f"    Do you want to proceed? (y/n): ")
    
    if confirm.lower() != 'y':
        print("⛔ Order Cancelled by User.")
        return

    # 5. Place Order
    print(f"\n[5] Sending Order for {symbol} at ${safe_price}...")
    
    try:
        # order_type="00" is Limit Order
        res = kis.place_order(symbol, "BUY", qty, price=safe_price, order_type="00")
        
        if res:
            print("\n✅ Order Placed Successfully!")
            print("   Response:", res)
            print("\nNOTE: Please check your KIS MTS/HTS mobile app to confirm the Open Order.")
            print("      Don't forget to CANCEL this test order manually!")
        else:
            print("\n❌ Order Placement Failed.")
            print("   Check the console logs above for 'ERROR' or 'WARNING' messages from KIS API.")
            print("   Common causes: Insufficient Balance, Market Closed, Invalid Token.")
    except Exception as e:
        print(f"\n❌ EXCEPTION during Order Placement: {e}")
        logger.exception("Detailed Exception Info:")

if __name__ == "__main__":
    try:
        test_order_logic()
    except Exception as e:
        print(f"\n❌ Critical Script Error: {e}")
        logger.exception("Critical Script Error")
