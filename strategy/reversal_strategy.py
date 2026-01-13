"""
전환 매매 전략 (Reverse/Flip Trading Strategy)
손실 포지션을 반대로 뒤집는 전략을 파라미터 기반으로 구현
"""
from pickle import TRUE
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
import sys
import os
import time
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    REVERSAL_STRATEGY_PARAMS,
    REVERSAL_STOP_LOSS_RATE,
    REVERSAL_TAKE_PROFIT_RATE,
    REVERSAL_REVERSE_TRIGGER,
    REVERSAL_REVERSE_MODE,
    REVERSAL_REVERSE_DELAY,
    REVERSAL_REVERSE_RISK_FACTOR,
    REVERSAL_MAX_HOLD_DAYS,
    REVERSAL_LOOKBACK_WINDOW,
    REVERSAL_VOLATILITY_THRESHOLD,
    REVERSAL_COOLDOWN_PERIOD,
    REVERSAL_REVERSAL_LIMIT,
    REVERSAL_MAX_DRAWDOWN,
    REVERSAL_TRAILING_STOP,
    REVERSAL_REVERSE_CONFIRMATION,
    REVERSAL_PRICE_MOMENTUM,
    REVERSAL_VOLUME_THRESHOLD,
    REVERSAL_MARKET_SENTIMENT_INDEX,
    get_etf_by_original
)
from strategy.indicators import TechnicalIndicators
from strategy.signal_generator import SignalGenerator, SignalType
from utils.logger import logger

class ReversalMode(Enum):
    """전환 방식"""
    FULL = "full"  # 전체 반전
    PARTIAL = "partial"  # 부분 반전

class ReversalStrategy:
    """전환 매매 전략 클래스"""
    
    def __init__(self, params: Optional[Dict] = None):
        """
        전환 매매 전략 초기화
        
        Args:
            params: 전략 파라미터 딕셔너리 (None이면 기본값 사용)
        """
        self.params = params or REVERSAL_STRATEGY_PARAMS.copy()
        self.indicators = TechnicalIndicators()
        
        # SignalGenerator에 rsi_oversold 파라미터 전달
        # optimize_rsi_threshold.py 등에서 "rsi_oversold" 키로 값을 넘길 예정
        rsi_oversold = self.params.get("rsi_oversold")
        self.signal_generator = SignalGenerator(rsi_oversold=rsi_oversold)
        
        # 전략 상태
        self.current_position = None  # "LONG", "SHORT", None
        self.current_etf_symbol = None  # 현재 보유 ETF
        self.entry_price = None
        self.entry_time = None
        self.entry_quantity = None
        self.capital = self.params.get("capital", 2000)
        self.initial_capital = self.capital
        
        # 전환 관련 상태
        self.last_reversal_time = None
        self.daily_reversal_count = 0
        self.last_reversal_date = None
        self.cooldown_until = None
        self.reversal_timestamps: List[datetime] = []  # 24시간 내 전환 기록
        
        # 거래 기록
        self.trade_history: List[Dict] = []
        self.reversal_history: List[Dict] = []
        
        logger.info(f"전환 매매 전략 초기화: {self.params}")
    
    def reset_daily_count(self):
        """일일 전환 횟수 리셋"""
        today = datetime.now().date()
        if self.last_reversal_date != today:
            self.daily_reversal_count = 0
            self.last_reversal_date = today
    
    def can_reverse(self) -> bool:
        """전환 가능 여부 확인"""
        self.reset_daily_count()
        
        # 일일 전환 횟수 제한
        if self.daily_reversal_count >= self.params.get("reversal_limit", 2):
            logger.warning(f"일일 전환 횟수 제한 도달: {self.daily_reversal_count}")
            return False
        
        # 쿨다운 기간 확인
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            logger.info(f"쿨다운 기간 중: {self.cooldown_until}")
            return False
        
        return True

    def reset_daily_count2(self, current_time: datetime):
        """일일 전환 횟수 리셋"""
        #today = datetime.now().date()
        if self.last_reversal_date != current_time:
            self.daily_reversal_count = 0
            self.last_reversal_date = current_time
    
    def can_reverse2(self, current_time: datetime) -> bool:
        """최근 24시간 기준 전환 가능 여부 확인"""
 
        self.reset_daily_count2(current_time)

        # 24시간 내 전환 기록만 남기기
        window_start = current_time - timedelta(hours=24)
        self.reversal_timestamps = [t for t in self.reversal_timestamps if t >= window_start]
        reversal_limit = self.params.get("reversal_limit", 2)
        if len(self.reversal_timestamps) >= reversal_limit:
            logger.warning(f"최근 24시간 전환 횟수 제한 도달: {len(self.reversal_timestamps)}")
            return False
        logger.info(f"최근 24시간 전환 횟수: {len(self.reversal_timestamps)} / {reversal_limit}")

        # 쿨다운 기간 확인
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        if self.cooldown_until and self.cooldown_until.tzinfo is None:
            self.cooldown_until = self.cooldown_until.replace(tzinfo=timezone.utc)
        if self.cooldown_until and current_time < self.cooldown_until:
            logger.info(f"쿨다운 기간 중: {self.cooldown_until}")
            return False
        
        return True

    def calculate_volatility(self, data: pd.DataFrame) -> float:
        """변동성 계산"""
        if len(data) < 2:
            return 0.0
        
        returns = data['close'].pct_change().dropna()
        volatility = returns.std()
        return float(volatility)
    
    def calculate_price_momentum(self, data: pd.DataFrame) -> float:
        """가격 모멘텀 계산 (전일 대비 상승률)"""
        if len(data) < 2:
            return 0.0
        
        current_price = data['close'].iloc[-1]
        previous_price = data['close'].iloc[-2]
        momentum = (current_price - previous_price) / previous_price
        return float(momentum)
    
    def calculate_volume_ratio(self, data: pd.DataFrame) -> float:
        """거래량 비율 계산 (평균 대비)"""
        if len(data) < self.params.get("lookback_window", 10):
            return 1.0
        
        lookback = self.params.get("lookback_window", 10)
        current_volume = data['volume'].iloc[-1]
        avg_volume = data['volume'].tail(lookback).mean()
        
        if avg_volume == 0:
            return 1.0
        
        return float(current_volume / avg_volume)
    
    def check_market_conditions(
        self,
        original_data: pd.DataFrame,
        etf_long_data: pd.DataFrame,
        etf_short_data: pd.DataFrame
    ) -> Dict[str, any]:
        """
        시장 조건 확인
        
        Returns:
            {
                "volatility": float,
                "price_momentum": float,
                "volume_ratio": float,
                "meets_threshold": bool
            }
        """
        volatility = self.calculate_volatility(original_data)
        price_momentum = self.calculate_price_momentum(original_data)
        volume_ratio = self.calculate_volume_ratio(original_data)
        
        # 임계값 확인
        meets_threshold = (
            volatility <= self.params.get("volatility_threshold", 0.03) and
            abs(price_momentum) >= self.params.get("price_momentum", 0.02) and
            volume_ratio >= self.params.get("volume_threshold", 1.5)
        )
        
        return {
            "volatility": volatility,
            "price_momentum": price_momentum,
            "volume_ratio": volume_ratio,
            "meets_threshold": meets_threshold
        }
    
    def check_reverse_confirmation(
        self,
        original_data: pd.DataFrame,
        target_side: str
    ) -> Tuple[bool, str]:
        """
        반전 진입 전 추가 확인 조건
        
        Args:
            original_data: 원본 주식 데이터
            target_side: 목표 포지션 ("LONG" or "SHORT")
        
        Returns:
            (확인 통과 여부, 이유)
        """
        if not self.params.get("reverse_confirmation", True):
            return True, "확인 조건 비활성화"
        
        try:
            # RSI 확인
            rsi = self.indicators.get_latest_rsi(original_data)
            if rsi is None:
                return False, "RSI 계산 실패"
            
            # MACD 확인
            macd = self.indicators.get_latest_macd(original_data)
            if macd is None:
                return False, "MACD 계산 실패"
            
            # 롱 포지션 전환 확인
            if target_side == "LONG":
                # RSI 과매도 또는 MACD 상승 신호
                if rsi < 40 or (macd.get("histogram", 0) > 0):
                    return True, f"RSI {rsi:.2f} + MACD 확인"
                return False, f"롱 전환 조건 미충족 (RSI: {rsi:.2f})"
            
            # 숏 포지션 전환 확인
            elif target_side == "SHORT":
                # RSI 과매수 또는 MACD 하락 신호
                if rsi > 60 or (macd.get("histogram", 0) < 0):
                    return True, f"RSI {rsi:.2f} + MACD 확인"
                return False, f"숏 전환 조건 미충족 (RSI: {rsi:.2f})"
            
            return False, "알 수 없는 포지션"
            
        except Exception as e:
            logger.error(f"반전 확인 실패: {e}")
            return False, f"오류: {str(e)}"
    
    def calculate_position_size(
        self,
        price: float,
        is_reversal: bool = False
    ) -> float:
        """
        포지션 크기 계산
        
        Args:
            price: 진입 가격
            is_reversal: 반전 거래 여부
        
        Returns:
            포지션 수량
        """
        # 반전 거래인 경우 리스크 팩터 적용
        risk_factor = 1.0
        if is_reversal:
            risk_factor = self.params.get("reverse_risk_factor", 0.8)
        
        # 사용 가능 자본 계산
        available_capital = self.capital * risk_factor
        
        # 기대수익 기준 계산 (간단화)
        # expected_profit = 150  # 목표 기대수익
        expected_profit = available_capital * 0.5  # 목표 기대수익
        take_profit_rate = self.params.get("take_profit_rate", 0.08)
        trade_amount = expected_profit / take_profit_rate
        
        # 사용 가능 자본 제한 (수수료 및 가격 변동 대비 버퍼 92%로 하향 조정)
        trade_amount = min(trade_amount, available_capital * 0.92)
        
        if trade_amount < 100:  # 최소 거래 금액
            return 0.0
        
        quantity = trade_amount / price
        return int(quantity)
    
    def execute_reversal(
        self,
        original_symbol: str,
        etf_long: str,
        etf_short: str,
        original_data: pd.DataFrame,
        etf_long_price: float,
        etf_short_price: float,
        current_time: datetime,
        reason: str = "전환 매매"
    ) -> Optional[Dict]:
        """
        전환 매매 실행
        
        Args:
            original_symbol: 원본 주식 심볼
            etf_long: 롱 ETF 심볼
            etf_short: 숏 ETF 심볼
            original_data: 원본 주식 데이터
            etf_long_price: 롱 ETF 현재가
            etf_short_price: 숏 ETF 현재가
            current_time: 
            reason: 전환 이유
        
        Returns:
            거래 결과 딕셔너리 또는 None
        """
        #if not self.can_reverse2(current_time):
        #    return None
        
        # 현재 포지션 확인
        if self.current_position is None:
            logger.warning("전환할 포지션이 없습니다")
            return None
        
        # 수수료율 가져오기 (기본값 0.001)
        fee_rate = self.params.get("fee_rate", 0.001)
        
        # 반전 확인 조건 체크
        target_side = "SHORT" if self.current_position == "LONG" else "LONG"
        confirmed = TRUE
        confirm_reason = "STOP LOSS REVERSE"
        #confirmed, confirm_reason = self.check_reverse_confirmation(original_data, target_side)
        
        #if not confirmed:
        #    logger.info(f"반전 확인 실패: {confirm_reason}")
        #    return None
        
        # 시장 조건 확인
        #market_conditions = self.check_market_conditions(
        #    original_data, 
        #    pd.DataFrame({'close': [etf_long_price], 'volume': [0]}),
        #    pd.DataFrame({'close': [etf_short_price], 'volume': [0]})
        #)
        
        #if not market_conditions["meets_threshold"]:
        #    logger.info(f"시장 조건 미충족: 변동성 {market_conditions['volatility']:.4f}")
        
        # 기존 포지션 청산
        if self.current_etf_symbol and self.entry_price and self.entry_quantity:
            exit_price = etf_long_price if self.current_position == "LONG" else etf_short_price
            trade_amount = self.entry_quantity * exit_price
            fee = trade_amount * fee_rate

            pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100

            #if self.current_position == "LONG":
            #    pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100
            #else:
            #    pnl_pct = ((self.entry_price - exit_price) / self.entry_price) * 100
            
            pnl = self.entry_quantity * self.entry_price * (pnl_pct / 100)
            
            # 청산 기록
            trade_record = {
                'entry_time': self.entry_time,
                #'exit_time': datetime.now(),
                'exit_time': current_time,
                'symbol': self.current_etf_symbol,
                'side': self.current_position,
                'entry_price': self.entry_price,
                'exit_price': exit_price,
                'quantity': self.entry_quantity,
                'pnl': pnl - fee,
                'pnl_pct': pnl_pct,
                'fee': fee,
                'reason': reason
            }
            self.trade_history.append(trade_record)
            
            # 자본 업데이트
            self.capital += self.entry_quantity * self.entry_price + pnl - fee
            
            logger.info(
                f"포지션 청산: [{current_time.strftime('%Y-%m-%d %H:%M')}] {self.current_etf_symbol} {self.current_position} "
                f"@ ${self.entry_price:.2f} ${exit_price:.2f} (손익: {pnl_pct:.2f}%, 수수료: ${fee:.2f})"
            )
        
        # 반전 지연 시간 적용
        if self.params.get("reverse_delay", 0) > 0:
            delay_seconds = self.params.get("reverse_delay", 60)
            logger.info(f"반전 지연: {delay_seconds}초 대기")
            time.sleep(min(delay_seconds, 5))  # 최대 5초만 대기 (테스트용)

        # 반대 포지션 진입
        target_etf = etf_long if target_side == "LONG" else etf_short
        target_price = etf_long_price if target_side == "LONG" else etf_short_price
        
        quantity = self.calculate_position_size(target_price, is_reversal=True)
        
        if quantity > 0:
            trade_amount = target_price * quantity
            fee = trade_amount * fee_rate
            self.capital -= (trade_amount + fee)
            
            # 전환 기록
            reversal_record = {
                #'time': datetime.now(),
                'time': current_time,
                'from_position': self.current_position,
                'to_position': target_side,
                'from_etf': self.current_etf_symbol,
                'to_etf': target_etf,
                'entry_price': target_price,
                'quantity': quantity,
                'fee': fee,
                'reason': reason,
                'confirm_reason': confirm_reason
            }
            self.reversal_history.append(reversal_record)
            
            # 상태 업데이트
            self.current_position = target_side
            self.current_etf_symbol = target_etf
            self.entry_price = target_price
            #self.entry_time = datetime.now()
            self.entry_time = current_time
            self.entry_quantity = quantity
            
            # 전환 카운트 및 쿨다운 설정
            self.daily_reversal_count += 1
            #self.last_reversal_time = datetime.now()
            self.last_reversal_time = current_time
            cooldown_days = self.params.get("cooldown_period", 1)
            #self.cooldown_until = datetime.now() + timedelta(days=cooldown_days)
            self.cooldown_until = current_time + timedelta(days=cooldown_days)
            
            self.reversal_timestamps.append(current_time)  # 24시간 내 전환 기록 추가
            
            logger.info(
                f"🔄 전환 매매 실행: [{current_time.strftime('%Y-%m-%d %H:%M')}] {reversal_record['from_etf']} -> {reversal_record['to_etf']} "
                f"({self.current_position}) @ ${target_price:.2f} x {quantity:.2f} (수수료: ${fee:.2f})"
            )
            
            return reversal_record
        
        return None
    
    def get_stop_loss_rate(self, etf_multiple:str) -> float:
        """포지션에 따른 손절율 반환"""
        if etf_multiple == "2" or etf_multiple == "-2":
            return self.params.get("2x_stop_loss_rate", -0.03) * 100
        else:
            return self.params.get("1x_stop_loss_rate", -0.015) * 100
            
    def check_stop_loss_take_profit(
        self,
        current_price: float
    ) -> Optional[str]:
        """
        손절/익절 조건 확인
        
        Returns:
            "STOP_LOSS", "TAKE_PROFIT", None
        """
        if not self.current_position or not self.entry_price:
            return None
        
        pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
        #if self.current_position == "LONG":
        #    pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
        #else:  # SHORT
        #    pnl_pct = ((self.entry_price - current_price) / self.entry_price) * 100
        
        stop_loss_rate = self.get_stop_loss_rate("2")  # 기본값 2x 기준
        take_profit_rate = self.params.get("take_profit_rate", 0.08) * 100
        
        if pnl_pct <= stop_loss_rate:
            return "STOP_LOSS"
        elif pnl_pct >= take_profit_rate:
            return "TAKE_PROFIT"
        
        return None

    def check_stop_loss_take_profit2(
        self,
        current_price: float,
        etf_multiple: str
    ) -> Optional[str]:
        """
        손절/익절 조건 확인
        
        Returns:
            "STOP_LOSS", "TAKE_PROFIT", None
        """
        if not self.current_position or not self.entry_price:
            return None
        
        print(f"self.entry_time: {self.entry_time.strftime('%Y-%m-%d %H:%M')}, self.current_etf_symbol: {self.current_etf_symbol}, self.current_position: {self.current_position}, self.entry_price: {self.entry_price:.2f}, current_price: {current_price:.2f}")
        pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
        #if self.current_position == "LONG":
        #    pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
        #else:  # SHORT
        #    pnl_pct = ((self.entry_price - current_price) / self.entry_price) * 100
        
        stop_loss_rate = self.get_stop_loss_rate(etf_multiple)
        take_profit_rate = self.params.get("take_profit_rate", 0.08) * 100
        
        if pnl_pct <= stop_loss_rate:
            return "STOP_LOSS"
        elif pnl_pct >= take_profit_rate:
            return "TAKE_PROFIT"
        
        return None

    def check_max_drawdown(self, current_etf_price: Optional[float] = None) -> bool:
        """최대 자본 손실률 확인"""
        max_drawdown_rate = self.params.get("max_drawdown", 0.05)
        
        # 현재 총 자산 가치 계산 (현금 + 포지션 가치)
        total_asset_value = self.capital
        if self.current_position and self.entry_quantity and current_etf_price:
            total_asset_value += (self.entry_quantity * current_etf_price)
            
        current_drawdown = (self.initial_capital - total_asset_value) / self.initial_capital
        
        if current_drawdown >= max_drawdown_rate:
            logger.warning(f"최대 자본 손실률 초과: {current_drawdown:.2%} >= {max_drawdown_rate:.2%}")
            return True
        
        return False
    
    def check_max_hold_days(self) -> bool:
        """최대 보유 기간 확인"""
        if not self.entry_time:
            return False
        
        if self.current_position is "LONG":    
            max_hold_days = self.params.get("long_max_hold_days", 2)
        else:
            max_hold_days = self.params.get("short_max_hold_days", 1)
        hold_duration = datetime.now(timezone.utc) - self.entry_time
        
        if hold_duration.days >= max_hold_days:
            logger.info(f"self.entry_time: {self.entry_time}")
            logger.info(f"datetime.now: {hold_duration}")
            logger.info(f"최대 보유 기간 초과: {hold_duration.days}일")
            return True
        
        return False

    def check_max_hold_days2(
        self,
        current_time: datetime) -> bool:
        """최대 보유 기간 확인"""
        if not self.entry_time:
            return False
        
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        if self.entry_time.tzinfo is None:
            self.entry_time = self.entry_time.replace(tzinfo=timezone.utc)
        else:
            self.entry_time = self.entry_time.replace(tzinfo=timezone.utc)

        if self.current_position is "LONG":    
            max_hold_days = self.params.get("long_max_hold_days", 2)
        else:
            max_hold_days = self.params.get("short_max_hold_days", 1)
        hold_duration = current_time - self.entry_time
        
        if hold_duration.days >= max_hold_days:
            logger.info(f"최대 보유 기간 초과: {hold_duration.days}일")
            return True
        
        return False
    
    def get_strategy_status(self) -> Dict:
        """전략 상태 조회"""
        return {
            "current_position": self.current_position,
            "current_etf": self.current_etf_symbol,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "quantity": self.entry_quantity,
            "capital": self.capital,
            "initial_capital": self.initial_capital,
            "daily_reversal_count": self.daily_reversal_count,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "total_trades": len(self.trade_history),
            "total_reversals": len(self.reversal_history)
        }

