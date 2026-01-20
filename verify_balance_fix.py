
import sys
import os
import time
from pprint import pprint

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading.kis_api import KisApi
from config.settings import PAPER_TRADING

def verify_fix():
    print("Verifying Multi-Exchange Balance Check Fix...")
    
    # Initialize API
    kis = KisApi(is_paper_trading=PAPER_TRADING)
    
    # Call the updated method
    print("\n[Calling kis.get_overseas_stock_balance()...]")
    start_time = time.time()
    data = kis.get_overseas_stock_balance()
    elapsed = time.time() - start_time
    
    print(f"Call took {elapsed:.2f} seconds")
    
    if data:
        print("\n--- Consolidated Holdings ---")
        holdings = data.get('holdings', [])
        if not holdings:
            print("No holdings found.")
        else:
            for item in holdings:
                print(f"[{item.get('ovrs_excg_cd')}] {item.get('ovrs_pdno')} {item.get('ovrs_item_name')} Qty:{item.get('ord_psbl_qty')}")
                # pprint(item) # Uncomment for full details
        
        print("\n--- Last Assets Info ---")
        assets = data.get('assets', {})
        pprint(assets)
        
        # Validation
        found_nvdx = False
        for item in holdings:
            if item.get('ovrs_pdno') == 'NVDX':
                found_nvdx = True
                break
        
        if found_nvdx:
             print("\n✅ SUCCESS: NVDX found in holdings!")
        else:
             print("\n❌ FAILURE: NVDX NOT found in holdings.")
    else:
        print("Failed to get balance data (None returned).")

if __name__ == "__main__":
    verify_fix()
