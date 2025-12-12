import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)

def get_base_url(mode="real"):
    """
    Returns the base URL for KIS API.
    :param mode: "real" or "paper" (virtual)
    """
    if mode == "real":
        return "https://openapi.koreainvestment.com:9443"
    else:
        return "https://openapivts.koreainvestment.com:29443"

def date_to_str(dt: datetime.datetime, fmt="%Y%m%d") -> str:
    """Converts datetime to string format required by API (YYYYMMDD)."""
    return dt.strftime(fmt)

def str_to_date(date_str: str, fmt="%Y%m%d") -> datetime.datetime:
    """Converts string to datetime."""
    return datetime.datetime.strptime(date_str, fmt)

async def rate_limited_sleep(requests_per_sec=1):
    """
    Helper to prevent hitting rate limits.
    Simple implementation: can be enhanced with a proper token bucket if needed.
    """
    # KIS API limit is roughly 20 calls/sec for some endpoints, but safer to go slower.
    # 0.1s sleep is usually safe for sequential calls in a loop.
    await asyncio.sleep(1.0 / requests_per_sec)

def format_ohlcv_colums(df):
    """Standardizes dataframe columns to lower case."""
    df.columns = [c.lower() for c in df.columns]
    return df
