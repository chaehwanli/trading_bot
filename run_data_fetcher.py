import asyncio
import logging
import os
import argparse
import json
from data_fetcher.auth import KisAuth
from data_fetcher.fetcher import KisFetcher
from data_fetcher.resampler import convert_interval
from backtester.engine import prepare_dataset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    try:
        with open("data_fetcher_config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load data_fetcher_config.json: {e}. Using defaults.")
        return {}

async def main():
    config = load_config()
    fetch_cfg = config.get("fetch", {})
    
    parser = argparse.ArgumentParser(description="KIS Data Fetcher & Backtest Prep")
    parser.add_argument("--symbols", nargs="+", default=fetch_cfg.get("symbols", ["005930"]), help="List of stock symbols")
    parser.add_argument("--interval", default=fetch_cfg.get("interval", "1h"), help="Interval (1m, 5m, 1h, 1d)")
    parser.add_argument("--period", default=fetch_cfg.get("period", "1y"), help="Period (1y, 7d, etc.)")
    parser.add_argument("--resample", action="store_true", help="Perform resampling demo")
    parser.add_argument("--source", type=str, choices=["kis", "yfinance"], default="kis", help="Data source: 'kis' or 'yfinance'")
    
    args = parser.parse_args()

    # Load Config (moved here as per snippet, though it was already loaded for defaults)
    config = load_config()
    
    # Init Fetcher
    if args.source == "kis":
        # 1. Auth
        try:
            auth = KisAuth()
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            logger.error("Please ensure .env has KIS_APP_KEY, KIS_APP_SECRET, KIS_ACC_NO")
            return
        fetcher = KisFetcher(auth)
        logger.info("[Source: KIS] Initialized.")
        logger.info(f"Starting download for {args.symbols}...")
        await fetcher.download_all(args.symbols, args.interval, args.period)
    else:
        from data_fetcher.yfinance_fetcher import YFinanceFetcher
        fetcher = YFinanceFetcher()
        logger.info("[Source: YFinance] Initialized.")
        # YFinance fetcher doesn't need auth, and period/interval logic might differ slightly,
        # but interface is aligned.
        # Note: fetcher.download_all is async in YFinanceFetcher wrapper
        logger.info(f"Starting download for {args.symbols}...")
        await fetcher.download_all(args.symbols, args.interval, args.period)
        
    
    # 3. Apply Indicators and Save
    # The user wants RSI/MACD in the saved CSV.
    ind_settings = config.get("indicators", {})
    logger.info(f"Applying indicators with settings: {ind_settings}")

    for sym in args.symbols:
        try:
            # Load raw data and calculate indicators using engine's prepare_dataset
            # This function adds RSI, MACD based on ind_settings
            # Note: prepare_dataset expects the file to exist (which we just downloaded)
            # We need to pass the source to find the file
            df = prepare_dataset(sym, args.interval, tz=None, ind_params=ind_settings, source=args.source)
            
            # Save back to CSV with indicators
            save_path = f"data/{args.source}/{sym}/{args.interval}.csv"
            df.to_csv(save_path)
            logger.info(f"Saved {sym} with indicators to {save_path}. Columns: {df.columns.tolist()}")
            
        except Exception as e:
            logger.error(f"Failed to apply indicators for {sym}: {e}")

    logger.info("Task completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted.")
