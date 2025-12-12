import pandas as pd

def convert_interval(df: pd.DataFrame, target_interval: str) -> pd.DataFrame:
    """
    Resamples the dataframe to the target interval.
    
    :param df: Input DataFrame (must have DatetimeIndex and ohlcv columns)
    :param target_interval: Target interval string (e.g., "5m", "1h", "1d")
    :return: Resampled DataFrame
    """
    if df.empty:
        return df

    # Map target_interval to pandas resample rule
    # pandas rules: T=min, H=hour, D=day
    rule_map = {
        "1m": "1T",
        "5m": "5T",
        "10m": "10T",
        "15m": "15T",
        "30m": "30T",
        "1h": "1H",
        "1d": "1D",
        "1w": "1W",
        "1mo": "1M"
    }
    
    rule = rule_map.get(target_interval, target_interval)
    
    # Check if we need to parse interval manually (e.g., if user passed "2h")
    # For now, rely on map or direct pandas compatibility if simple
    
    aggregation = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    # Resample
    resampled_df = df.resample(rule).agg(aggregation)
    
    # Drop rows with NaN (if any, though time gaps might produce them, we usually want to keep or drop depending on strategy)
    # Usually for OHLCV, if no trades, we might drop or forward fill.
    # Standard practice: Drop empty bins (market closed)
    resampled_df.dropna(inplace=True)
    
    return resampled_df
