"""
매매 신호 생성 모듈
"""
import pandas as pd
from typing import Optional, Dict
from enum import Enum
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategy.indicators import TechnicalIndicators
from config.settings import (
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT, RSI_MIDDLE,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL
)
from utils.logger import logger

class SignalType(Enum):
    """매매 신호 타입"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"

class PositionSignalType(Enum):
    """매매 신호 타입"""
    LONO = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    CLOSE = "CLOSE"

class SignalGenerator:
    """매매 신호 생성 클래스"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def generate_signal(
        self, 
        data: pd.DataFrame,
        current_position: Optional[str] = None
    ) -> Dict[str, any]:
        """
        RSI/MACD 기반 매매 신호 생성
        
        Args:
            data: 가격 데이터
            current_position: 현재 포지션 ("LONG", "SHORT", None)
        
        Returns:
            {
                "signal": SignalType,
                "rsi": float,
                "macd": dict,
                "confidence": float,
                "reason": str
            }
        """
        try:
            if data is None or len(data) < 50:
                return {
                    "signal": SignalType.HOLD,
                    "rsi": None,
                    "macd": None,
                    "confidence": 0.0,
                    "reason": "데이터 부족"
                }
            
            # RSI 계산
            rsi = self.indicators.get_latest_rsi(data, RSI_PERIOD)
            
            # MACD 계산
            macd_data = self.indicators.get_latest_macd(
                data, MACD_FAST, MACD_SLOW, MACD_SIGNAL
            )
            
            if rsi is None or macd_data is None:
                return {
                    "signal": SignalType.HOLD,
                    "rsi": rsi,
                    "macd": macd_data,
                    "confidence": 0.0,
                    "reason": "지표 계산 실패"
                }
            
            signal, confidence, reason = self._analyze_signals2(
                rsi, macd_data, current_position
            )
            
            return {
                "signal": signal,
                "rsi": rsi,
                "macd": macd_data,
                "confidence": confidence,
                "reason": reason
            }
            
        except Exception as e:
            logger.error(f"신호 생성 실패: {e}")
            return {
                "signal": SignalType.HOLD,
                "rsi": None,
                "macd": None,
                "confidence": 0.0,
                "reason": f"오류: {str(e)}"
            }
    
    def _analyze_signals(
        self,
        rsi: float,
        macd: Dict[str, float],
        current_position: Optional[str]
    ) -> tuple:
        """
        RSI와 MACD를 종합하여 신호 분석
        
        Returns:
            (SignalType, confidence, reason)
        """
        macd_line = macd["macd"]
        signal_line = macd["signal"]
        histogram = macd["histogram"]
        
        # MACD 골든크로스/데드크로스 확인
        macd_bullish = macd_line > signal_line and histogram > 0
        macd_bearish = macd_line < signal_line and histogram < 0
        
        # RSI 과매수/과매도 확인
        rsi_oversold = rsi < RSI_OVERSOLD
        rsi_overbought = rsi > RSI_OVERBOUGHT
        rsi_neutral = RSI_OVERSOLD <= rsi <= RSI_OVERBOUGHT
        
        # 현재 포지션이 없는 경우
        if current_position is None:
            # 매수 신호: RSI 과매도 + MACD 상승 전환
            if rsi_oversold and macd_bullish:
                return SignalType.BUY, 0.8, "RSI 과매도 + MACD 상승 전환"
            
            # 매수 신호: RSI 중립 + MACD 강한 상승
            if rsi_neutral and macd_bullish: #and histogram > 0.5:
                return SignalType.BUY, 0.6, "MACD 강한 상승 모멘텀"
            
            # 매도 신호: RSI 과매수 + MACD 하락 전환
            if rsi_overbought and macd_bearish:
                return SignalType.SELL, 0.8, "RSI 과매수 + MACD 하락 전환"
            
            # 매도 신호: RSI 중립 + MACD 강한 하락
            if rsi_neutral and macd_bearish: #and histogram < -0.5:
                return SignalType.SELL, 0.6, "MACD 강한 하락 모멘텀"
        
        # 현재 LONG 포지션인 경우
        elif current_position == "LONG":
            # 반대 신호 (포지션 전환): RSI 과매수 + MACD 하락
            if rsi_overbought and macd_bearish:
                return SignalType.SELL, 0.7, "LONG 포지션 전환: RSI 과매수 + MACD 하락"
            
            # 포지션 유지
            if rsi_neutral and macd_bullish:
                return SignalType.HOLD, 0.5, "LONG 포지션 유지"
        
        # 현재 SHORT 포지션인 경우
        elif current_position == "SHORT":
            # 반대 신호 (포지션 전환): RSI 과매도 + MACD 상승
            if rsi_oversold and macd_bullish:
                return SignalType.BUY, 0.7, "SHORT 포지션 전환: RSI 과매도 + MACD 상승"
            
            # 포지션 유지
            if rsi_neutral and macd_bearish:
                return SignalType.HOLD, 0.5, "SHORT 포지션 유지"
        
        # 기본값: 보유
        return SignalType.HOLD, 0.3, "신호 없음"

    def _analyze_signals2(
        self,
        rsi: float,
        macd: Dict[str, float],
        current_position: Optional[str]
    ) -> tuple:
        """
        RSI와 MACD를 종합하여 신호 분석
        
        Returns:
            (SignalType, confidence, reason)
        """
        macd_line = macd["macd"]
        signal_line = macd["signal"]
        histogram = macd["histogram"]
        
        # MACD 골든크로스/데드크로스 확인
        macd_bullish = macd_line > signal_line and histogram > 0
        macd_bearish = macd_line < signal_line and histogram < 0
        
        # RSI 과매수/과매도 확인
        rsi_oversold = rsi < RSI_OVERSOLD
        rsi_overbought = rsi > RSI_OVERBOUGHT
        rsi_neutral_bought = (RSI_MIDDLE) <= rsi <= (RSI_OVERBOUGHT)
        rsi_neutral_sold = (RSI_OVERSOLD) <= rsi <= (RSI_MIDDLE - (1))
        rsi_neutral = RSI_OVERSOLD <= rsi <= RSI_OVERBOUGHT
        
        # 현재 포지션이 없는 경우
        if current_position is None:
            # 매수 신호: RSI 과매도 + MACD 상승 전환
            if rsi_oversold and macd_bullish:
                return SignalType.HOLD, 0.5, "RSI 과매도 + MACD 상승 전환"
            
            # 매수 신호: RSI 중립 + MACD 강한 상승
            if rsi_neutral_sold and macd_bullish: #and histogram > 0.5:
                return SignalType.BUY, 0.8, "MACD 강한 상승 모멘텀"
            
            # 매도 신호: RSI 과매수 + MACD 하락 전환
            if rsi_overbought and macd_bearish:
                return SignalType.HOLD, 0.5, "RSI 과매수 + MACD 하락 전환"
            
            # 매도 신호: RSI 중립 + MACD 강한 하락
            if rsi_neutral_bought and macd_bearish: #and histogram < -0.5:
                return SignalType.SELL, 0.8, "MACD 강한 하락 모멘텀"
        
        # 현재 LONG 포지션인 경우
        elif current_position == "LONG":
            # 반대 신호 (포지션 전환): RSI 과매수 + MACD 하락
            if rsi_overbought and macd_bearish and histogram < -0.5:
                return SignalType.SELL, 0.7, "LONG 포지션 전환: RSI 과매수 + MACD 하락"
            
            # 포지션 유지
            if rsi_neutral and macd_bullish:
                return SignalType.HOLD, 0.5, "LONG 포지션 유지"
        
        # 현재 SHORT 포지션인 경우
        elif current_position == "SHORT":
            # 반대 신호 (포지션 전환): RSI 과매도 + MACD 상승
            if rsi_oversold and macd_bullish and histogram > 0.5:
                return SignalType.SELL, 0.7, "SHORT 포지션 전환: RSI 과매도 + MACD 상승"
            
            # 포지션 유지
            if rsi_neutral and macd_bearish:
                return SignalType.HOLD, 0.5, "SHORT 포지션 유지"
        
        # 기본값: 보유
        return SignalType.HOLD, 0.3, "신호 없음"

