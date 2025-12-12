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
    
    args = parser.parse_args()

    # 1. Auth
    try:
        auth = KisAuth()
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        logger.error("Please ensure .env has KIS_APP_KEY, KIS_APP_SECRET, KIS_ACC_NO")
        return

    # 2. Fetch Data
    fetcher = KisFetcher(auth)
    logger.info(f"Starting download for {args.symbols}...")
    
    await fetcher.download_all(args.symbols, args.interval, args.period)
    
    # 3. Resample Demo (Optional) / process demo
    # Even if not resampling, we can show "Processing" result if we want demo
    # But for now keep --resample flag as trigger to show loaded data
    if args.resample:
        ind_settings = config.get("indicators", {})
        for sym in args.symbols:
            # Load the just fetched data
            # Typically helper needed purely for loading raw generic df, 
            # but we can use prepare_dataset logic or direct pandas read.
            try:
                # Reuse prepare_dataset to load clean df
                df = prepare_dataset(sym, args.interval, tz=None, ind_params=ind_settings) 
                
                logger.info(f"Loaded {sym} with indicators. Columns: {df.columns.tolist()}")
                if 'rsi' in df.columns:
                    logger.info(f"RSI tail: {df['rsi'].tail(1).values}")
                
                # Resample 1h -> 1d for demo
                tgt = "1d"
                resampled = convert_interval(df, tgt)
                
                logger.info(f"Resampled {sym}: {args.interval} -> {tgt} (Rows: {len(df)} -> {len(resampled)})")
                
                # Save resampled
                save_path = f"data/{sym}/{tgt}.csv"
                resampled.to_csv(save_path)
                logger.info(f"Saved resampled data to {save_path}")
                
            except Exception as e:
                logger.error(f"Resampling failed for {sym}: {e}")

    logger.info("Task completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted.")
