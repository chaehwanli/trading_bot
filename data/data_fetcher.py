"""
시장 데이터 수집 모듈
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import logger

class DataFetcher:
    """시장 데이터 수집 클래스"""
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = timedelta(minutes=1)  # 1분 캐시
    
    def get_realtime_price(self, symbol: str) -> Optional[float]:
        """실시간 가격 조회"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")
            
            if data.empty:
                logger.warning(f"{symbol}: 데이터 없음")
                return None
            
            latest_price = data['Close'].iloc[-1]
            logger.debug(f"{symbol} 현재가: ${latest_price:.2f}")
            return float(latest_price)
            
        except Exception as e:
            logger.error(f"{symbol} 가격 조회 실패: {e}")
            return None
    
    def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1mo",
        interval: str = "1h"
    ) -> Optional[pd.DataFrame]:
        """과거 데이터 조회"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                logger.warning(f"{symbol}: 과거 데이터 없음")
                return None
            
            # 컬럼명 정리
            data.columns = [col.lower().replace(' ', '_') for col in data.columns]
            
            logger.debug(f"{symbol} 과거 데이터 조회 성공: {len(data)}개")
            return data
            
        except Exception as e:
            logger.error(f"{symbol} 과거 데이터 조회 실패: {e}")
            return None
    
    def get_intraday_data(
        self, 
        symbol: str, 
        interval: str = "5m"
    ) -> Optional[pd.DataFrame]:
        """당일 분봉 데이터 조회"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval=interval)
            
            if data.empty:
                return None
            
            data.columns = [col.lower().replace(' ', '_') for col in data.columns]
            return data
            
        except Exception as e:
            logger.error(f"{symbol} 분봉 데이터 조회 실패: {e}")
            return None
    
    def get_market_status(self, symbol: str) -> Dict[str, any]:
        """시장 상태 정보 조회"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                "symbol": symbol,
                "market_state": info.get("marketState", "UNKNOWN"),
                "regular_market_price": info.get("regularMarketPrice"),
                "previous_close": info.get("previousClose"),
                "volume": info.get("volume"),
            }
        except Exception as e:
            logger.error(f"{symbol} 시장 상태 조회 실패: {e}")
            return {}

