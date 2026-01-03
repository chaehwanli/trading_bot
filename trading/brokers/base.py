from abc import ABC, abstractmethod
from typing import Optional, Dict

class BaseBroker(ABC):
    """모든 증권사 브로커 클래스의 추상 기본 클래스"""

    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[float]:
        """현재가 조회"""
        pass

    @abstractmethod
    def get_balance(self) -> float:
        """계좌 예수금 조회 (USD)"""
        pass

    @abstractmethod
    def get_minute_price(self, symbol: str, interval_min: int = 60):
        """분봉 데이터 조회"""
        pass

    @abstractmethod
    def place_order(self, symbol: str, side: str, qty: float, price: float = 0, order_type: str = "00") -> Optional[Dict]:
        """주문 실행"""
        pass
    
    @abstractmethod
    def ensure_valid_token(self):
        """토큰/세션 유효성 확인"""
        pass
