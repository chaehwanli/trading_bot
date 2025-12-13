import yfinance as yf
import pandas as pd
import os
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class YFinanceFetcher:
    def __init__(self):
        pass

    async def download_all(self, symbols, interval, period="1y"):
        """
        Fetches OHLCV data for given symbols using yfinance.
        :param symbols: List of symbol strings
        :param interval: "1m", "1h", "1d", etc. 
                         (YFinance supports: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        :param period: "1y", "1d", etc.
        """
        # Map generic interval to yfinance interval if needed
        # Our config usually has "1h", "1d" which matches yfinance.
        
        for symbol in symbols:
            try:
                # Run sync yfinance in async loop executor to avoid blocking if needed, 
                # but yf.download is blocking. For simple script it's usually fine or we wrap it.
                # Since we want to update UI/log, sequential is fine.
                
                logger.info(f"Fetching {symbol} ({interval}) from YFinance (period={period})...")
                
                # YF period valid options: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
                # If period is not valid, default to 1y? Or try standard.
                # "max" is valid.
                
                # Note: yfinance auto-adjusts? We usually want adjusted close for validation?
                # or raw? KIS gives raw usually?
                # default auto_adjust=False in older versions, True in newer?
                # Let's set auto_adjust=True to get clean prices for backtest
                
                df = yf.download(
                    tickers=symbol, 
                    period=period, 
                    interval=interval, 
                    auto_adjust=False, # Getting raw OHLC + Adj Close usually better? 
                                       # Actually backtester often uses 'Close'. 
                                       # If we use auto_adjust=True, 'Close' is adjusted. 
                                       # Let's use auto_adjust=True for simplicity.
                    progress=False
                )
                
                if df.empty:
                    logger.warning(f"No data found for {symbol}")
                    continue
                
                # Create standard dataframe structure
                # yfinance MultiIndex columns if single ticker?
                # If single ticker, columns are just Open, High...
                # If updated yf, it might return MultiIndex regardless.
                
                if isinstance(df.columns, pd.MultiIndex):
                     # Extract level if symbol is top level
                     # Usually for single download it might be (Price, Ticker) or just Price
                     # Let's check.
                     # Recent yfinance often keeps Ticker level even for single.
                     try:
                         df = df.xs(symbol, axis=1, level=1)
                     except:
                         pass # Maybe not multiindex or different structure
                
                # Normalize columns
                df.columns = [c.lower() for c in df.columns]
                # rename "adj close" -> "adj_close" if exists
                # If auto_adjust=True, 'close' is already adjusted? 
                # Wait, auto_adjust=True replaces Open/High/Low/Close with adjusted values.
                
                # Ensure we have ohlcv
                if 'volume' not in df.columns:
                    df['volume'] = 0
                
                # Reset index to get datetime column if it's index
                if isinstance(df.index, pd.DatetimeIndex):
                    df.index.name = 'datetime'
                    # Standardize Timezone to KST (Asia/Seoul) to match KIS data
                    # YFinance usually returns UTC or America/New_York
                    # We convert to Asia/Seoul
                    if df.index.tz is None:
                        # If naive, assume UTC if coming from yf with auto_adjust? 
                        # Usually YF is timezone aware these days. 
                        # If naive, localize to UTC first then convert.
                        df.index = df.index.tz_localize('UTC')
                    
                    df.index = df.index.tz_convert('Asia/Seoul')
                
                # Save
                self._save_data(symbol, interval, df)
                
                # Rate limit? YF is lenient but let's be nice.
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to fetch {symbol} from YFinance: {e}")

    def _save_data(self, symbol, interval, df):
        dir_path = f"data/yfinance/{symbol}"
        os.makedirs(dir_path, exist_ok=True)
        file_path = f"{dir_path}/{interval}.csv"
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        df.to_csv(file_path)
        logger.info(f"Saved {symbol} to {file_path} ({len(df)} rows)")
