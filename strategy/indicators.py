"""
기술적 지표 계산 모듈
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import logger
from config.settings import (
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL
)

class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def calculate_rsi(data: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """RSI 계산"""
        try:
            if len(data) < period + 1:
                logger.warning(f"RSI 계산: 데이터 부족 (필요: {period + 1}, 현재: {len(data)})")
                return None
            
            close = data['close'] if 'close' in data.columns else data['Close']
            delta = close.diff()
            
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"RSI 계산 실패: {e}")
            return None
    
    @staticmethod
    def calculate_macd(
        data: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Optional[Tuple[pd.Series, pd.Series, pd.Series]]:
        """MACD 계산 (MACD, Signal, Histogram)"""
        try:
            if len(data) < slow + signal:
                logger.warning(f"MACD 계산: 데이터 부족")
                return None
            
            close = data['close'] if 'close' in data.columns else data['Close']
            
            # EMA 계산
            ema_fast = close.ewm(span=fast, adjust=False).mean()
            ema_slow = close.ewm(span=slow, adjust=False).mean()
            
            # MACD 라인
            macd = ema_fast - ema_slow
            
            # Signal 라인
            signal_line = macd.ewm(span=signal, adjust=False).mean()
            
            # Histogram
            histogram = macd - signal_line
            
            return macd, signal_line, histogram
            
        except Exception as e:
            logger.error(f"MACD 계산 실패: {e}")
            return None
    
    @staticmethod
    def get_latest_rsi(data: pd.DataFrame, period: int = RSI_PERIOD) -> Optional[float]:
        """최신 RSI 값 반환"""
        rsi = TechnicalIndicators.calculate_rsi(data, period)
        if rsi is not None and not rsi.empty:
            return float(rsi.iloc[-1])
        return None
    
    @staticmethod
    def get_latest_macd(
        data: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Optional[dict]:
        """최신 MACD 값 반환"""
        result = TechnicalIndicators.calculate_macd(data, fast, slow, signal)
        if result is None:
            return None
        
        macd, signal_line, histogram = result
        
        return {
            "macd": float(macd.iloc[-1]),
            "signal": float(signal_line.iloc[-1]),
            "histogram": float(histogram.iloc[-1])
        }

