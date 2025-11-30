"""
포지션 관리 모듈
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    MAX_POSITION_HOLD_DAYS,
    FORCE_CLOSE_HOUR,
    STOP_LOSS_PCT,
    TAKE_PROFIT_MIN_PCT,
    TAKE_PROFIT_MAX_PCT
)
from utils.logger import logger

class Position:
    """포지션 클래스"""
    
    def __init__(
        self,
        symbol: str,
        side: str,  # "LONG" or "SHORT"
        entry_price: float,
        quantity: float,
        entry_time: datetime
    ):
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_time = entry_time
        self.current_price = entry_price
        self.last_update = entry_time
    
    def update_price(self, current_price: float):
        """현재 가격 업데이트"""
        self.current_price = current_price
        self.last_update = datetime.now()
    
    def get_pnl_pct(self) -> float:
        """손익률 계산 (%)"""
        if self.side == "LONG":
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        else:  # SHORT
            return ((self.entry_price - self.current_price) / self.entry_price) * 100
    
    def get_pnl_amount(self) -> float:
        """손익 금액 계산"""
        pnl_pct = self.get_pnl_pct() / 100
        return self.entry_price * self.quantity * pnl_pct
    
    def should_stop_loss(self) -> bool:
        """손절 조건 확인"""
        return self.get_pnl_pct() <= STOP_LOSS_PCT * 100
    
    def should_take_profit(self) -> bool:
        """익절 조건 확인"""
        pnl_pct = self.get_pnl_pct()
        return TAKE_PROFIT_MIN_PCT * 100 <= pnl_pct <= TAKE_PROFIT_MAX_PCT * 100
    
    def should_force_close(self) -> bool:
        """강제 청산 조건 확인 (시간 기준)"""
        now = datetime.now()
        hold_duration = now - self.entry_time
        
        # 최대 보유 기간 초과
        if hold_duration.days >= MAX_POSITION_HOLD_DAYS:
            return True
        
        # 익일 오전 강제 매도 시간 확인
        if now.hour >= FORCE_CLOSE_HOUR and now.date() > self.entry_time.date():
            return True
        
        return False
    
    def to_dict(self) -> Dict:
        """포지션 정보를 딕셔너리로 변환"""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "quantity": self.quantity,
            "entry_time": self.entry_time.isoformat(),
            "pnl_pct": self.get_pnl_pct(),
            "pnl_amount": self.get_pnl_amount(),
            "hold_duration": str(datetime.now() - self.entry_time)
        }

class PositionManager:
    """포지션 관리자"""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}  # symbol -> Position
    
    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float
    ) -> Optional[Position]:
        """포지션 오픈"""
        try:
            # 기존 포지션이 있으면 먼저 청산
            if symbol in self.positions:
                logger.warning(f"{symbol} 기존 포지션 존재, 먼저 청산 필요")
                return None
            
            position = Position(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                quantity=quantity,
                entry_time=datetime.now()
            )
            
            self.positions[symbol] = position
            logger.info(f"포지션 오픈: {symbol} {side} @ ${entry_price:.2f} x {quantity}")
            
            return position
            
        except Exception as e:
            logger.error(f"포지션 오픈 실패: {e}")
            return None
    
    def close_position(self, symbol: str) -> Optional[Position]:
        """포지션 청산"""
        if symbol not in self.positions:
            logger.warning(f"{symbol} 포지션 없음")
            return None
        
        position = self.positions.pop(symbol)
        pnl = position.get_pnl_amount()
        pnl_pct = position.get_pnl_pct()
        
        logger.info(
            f"포지션 청산: {symbol} {position.side} "
            f"손익: ${pnl:.2f} ({pnl_pct:.2f}%)"
        )
        
        return position
    
    def update_position_price(self, symbol: str, current_price: float):
        """포지션 가격 업데이트"""
        if symbol in self.positions:
            self.positions[symbol].update_price(current_price)
    
    def check_exit_conditions(self, symbol: str) -> Optional[str]:
        """
        청산 조건 확인
        
        Returns:
            "STOP_LOSS", "TAKE_PROFIT", "FORCE_CLOSE", None
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        if position.should_stop_loss():
            return "STOP_LOSS"
        
        if position.should_take_profit():
            return "TAKE_PROFIT"
        
        if position.should_force_close():
            return "FORCE_CLOSE"
        
        return None
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """포지션 조회"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> Dict[str, Position]:
        """모든 포지션 조회"""
        return self.positions.copy()
    
    def has_position(self, symbol: str) -> bool:
        """포지션 보유 여부"""
        return symbol in self.positions

