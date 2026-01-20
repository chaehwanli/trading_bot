
import sys
import os
import json
from pprint import pprint
import requests
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading.kis_api import KisApi
from config.settings import PAPER_TRADING

def debug_balance():
    print(f"Current Mode: {'Paper Trading' if PAPER_TRADING else 'Real Trading'}")
    
    # Force Token Refresh - COMMENTED OUT to avoid 403 on repeated runs
    # token_file = "kis_token_paper.json" if PAPER_TRADING else "kis_token_real.json"
    # if os.path.exists(token_file):
    #     os.remove(token_file)
    #     print(f"Deleted cached token file: {token_file}")
    # else:
    #     print(f"No cached token file found: {token_file}")
    
    # Initialize API
    kis = KisApi(is_paper_trading=PAPER_TRADING)
    
    print(f"Account: {kis.account_no}")
    
    # 1. Check Balance (Holdings & Assets)
    for exch in ["NAS", "AMS", "NYS", "AMEX"]:
        print(f"\n[Calling get_overseas_stock_balance for {exch}]...")
        
        # Define a custom method to specify exchange code
        def custom_get_balance(self, exch_cd="NAS"):
            path = "/uapi/overseas-stock/v1/trading/inquire-balance"
            url = f"{self.base_url}{path}"
            tr_id = "VTTT3012R" if self.is_paper_trading else "TTTT3012R"
            headers = self._get_common_headers(tr_id)
            params = {
                "CANO": self.account_front,
                "ACNT_PRDT_CD": self.account_back,
                "OVRS_EXCG_CD": exch_cd,
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": ""
            }
            try:
                res = requests.get(url, headers=headers, params=params)
                res.raise_for_status()
                return res.json()
            except Exception as e:
                print(f"Error for {exch_cd}: {e}")
                return None

        data = custom_get_balance(kis, exch)
        
        if data:
            if data['rt_cd'] != '0':
                print(f"Failed: {data['msg1']}")
                continue
                
            print(f"--- Assets ({exch}) ---")
            pprint(data.get('output2'))
            
            print(f"--- Holdings ({exch}) ---")
            holdings = data.get('output1', [])
            if not holdings:
                print("No holdings found.")
            for item in holdings:
                pprint(item)
        else:
            print("Failed to get balance data.")

    # 2. Check Transaction History
    print("\n[Checking Transaction History (20260115 - 20260117)]...")
    
    def custom_get_trades(self, exch_cd="NAS"):
        path = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
        url = f"{self.base_url}{path}"
        tr_id = "VTTS3035R" if self.is_paper_trading else "TTTS3035R"
        headers = self._get_common_headers(tr_id)
        
        # Date range extended to include possible timezone diffs
        start_dt = "20260115"
        end_dt = "20260117"
        
        params = {
            "CANO": self.account_front,
            "ACNT_PRDT_CD": self.account_back,
            "OVRS_EXCG_CD": exch_cd,
            "TR_CRCY_CD": "USD",
            "PDNO": "", # All items
            "ORD_DT": "",
            "ORD_STRT_DT": start_dt,
            "ORD_END_DT": end_dt, # KIS often requires same start/end to be performant, but here we scan
            "INQR_DVSN": "00",          # 00: 역순 (최신순) - Default is usually 00
            "SLL_BUY_DVSN": "00",
            "CCLD_NCCS_DVSN": "00",     # 00: Total (Finished + Unfinished)
            "SORT_SQN": "DS", 
            "ORD_GNO_BRNO": "", 
            "ODNO": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        try:
            res = requests.get(url, headers=headers, params=params)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Error for trades {exch_cd}: {e}")
            return None

    exch_map = {"NAS": "NASDAQ", "AMS": "AMEX (AMS)", "NYS": "NYSE"}
    for exch in ["NAS", "AMS", "NYS"]:
        label = exch_map.get(exch, exch)
        print(f"\nScanning trades for {label}...")
        data = custom_get_trades(kis, exch)
        if data and data['rt_cd'] == '0':
            trades = data.get('output', [])
            if trades:
                # Print raw object to debug
                for t in trades:
                    pprint(t)
            else:
                print("No trades found.")
        else:
            msg = data['msg1'] if data else "Unknown error"
            print(f"Failed: {msg}")

if __name__ == "__main__":
    debug_balance()
