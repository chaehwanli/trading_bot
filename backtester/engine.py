import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

def prepare_dataset(symbol: str, interval: str, tz: str = "UTC", ind_params: dict = None, source: str = "kis") -> pd.DataFrame:
    """
    Prepares a dataset for backtesting.
    :param ind_params: Dictionary of indicator parameters (e.g. {'rsi': {'length': 5}})
    :param source: 'kis' or 'yfinance'
    """
    if ind_params is None:
        ind_params = {}

    file_path = f"data/{source}/{symbol}/{interval}.csv"
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file for {symbol} ({interval}) not found at {file_path}")
    
    df = pd.read_csv(file_path)
    
    # Parse datetime
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
    
    # Sort
    df.sort_index(inplace=True)
    
    # Localize/Convert TZ
    # KIS data is usually KST (Asia/Seoul)
    # If the CSV didn't save offset, assume KST
    if df.index.tz is None:
        df.index = df.index.tz_localize('Asia/Seoul')
    
    if tz:
        df.index = df.index.tz_convert(tz)
    
    # Drop duplicates
    df = df[~df.index.duplicated(keep='last')]
    
    # Connect Pandas TA
    try:
        import pandas_ta as ta
        
        # RSI
        rsi_len = ind_params.get('rsi', {}).get('length', 14)
        df.ta.rsi(length=rsi_len, append=True)
        
        # MACD
        macd_cfg = ind_params.get('macd', {})
        df.ta.macd(fast=macd_cfg.get('fast', 12), 
                   slow=macd_cfg.get('slow', 26), 
                   signal=macd_cfg.get('signal', 9), 
                   append=True)
        
        # Rename MACD columns to lowercase if needed or standard 'macd', 'macd_signal', 'macd_hist'
        # pandas_ta default names: MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
        # Normalize
        # We need to explicitly find valid cols because len might change numbers in name
        
        # Dynamic rename based on config
        fast = macd_cfg.get('fast', 12)
        slow = macd_cfg.get('slow', 26)
        sig = macd_cfg.get('signal', 9)
        
        df.rename(columns={
            f"RSI_{rsi_len}": "rsi",
            f"MACD_{fast}_{slow}_{sig}": "macd",
            f"MACDs_{fast}_{slow}_{sig}": "macd_signal",
            f"MACDh_{fast}_{slow}_{sig}": "macd_hist"
        }, inplace=True)
        
    except ImportError:
        logger.warning("pandas_ta not installed. RSI/MACD skipped.")
    except Exception as e:
        logger.error(f"Failed to calculate indicators: {e}")
    
    # Basic data integrity check
    # Close should not be 0 or NaN
    df = df[df['close'] > 0]
    df.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)
    
    logger.info(f"Prepared {len(df)} records for {symbol} ({interval}) in {tz} with indicators")

    
    return df
