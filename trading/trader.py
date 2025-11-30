"""
거래 실행 모듈
"""
from typing import Optional, Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    API_KEY, API_SECRET, BASE_URL,
    PAPER_TRADING, DRY_RUN,
    POSITION_SIZE_PCT, MIN_TRADE_AMOUNT,
    EXPECTED_PROFIT_TARGET, TAKE_PROFIT
)
from trading.position_manager import PositionManager, Position
from utils.logger import logger

class Trader:
    """거래 실행 클래스"""
    
    def __init__(self, initial_capital: float = 2000.0):
        self.position_manager = PositionManager()
        self.capital = initial_capital
        self.available_capital = initial_capital
        self.dry_run = DRY_RUN
        
        # 실제 API 연결은 여기서 초기화
        # 예: self.api = alpaca.REST(API_KEY, API_SECRET, BASE_URL)
        logger.info(f"Trader 초기화: 자본 ${self.capital:.2f}, DRY_RUN={self.dry_run}")
    
    def get_account_balance(self) -> float:
        """계좌 잔고 조회"""
        if self.dry_run:
            return self.available_capital
        
        # 실제 API 호출
        # account = self.api.get_account()
        # return float(account.cash)
        return self.available_capital
    
    def calculate_position_size(
        self,
        price: float,
        capital: Optional[float] = None,
        expected_profit: Optional[float] = None
    ) -> float:
        """
        포지션 크기 계산
        
        Args:
            price: 진입 가격
            capital: 사용 가능 자본 (None이면 현재 잔고 사용)
            expected_profit: 기대수익 금액 (None이면 설정값 사용)
        
        Returns:
            포지션 수량
        """
        if capital is None:
            capital = self.get_account_balance()
        
        if expected_profit is None:
            expected_profit = EXPECTED_PROFIT_TARGET
        
        # 기대수익 기준으로 진입 금액 계산
        # 예: 목표수익 $150, target% = 8% → 진입금액 = 150 / 0.08 = $1875
        trade_amount = expected_profit / TAKE_PROFIT
        
        # 최소 거래 금액 체크
        if trade_amount < MIN_TRADE_AMOUNT:
            logger.warning(f"거래 금액 부족: ${trade_amount:.2f} < ${MIN_TRADE_AMOUNT}")
            return 0.0
        
        # 사용 가능 자본 제한
        max_trade_amount = capital * POSITION_SIZE_PCT
        trade_amount = min(trade_amount, max_trade_amount)
        
        quantity = trade_amount / price
        return round(quantity, 2)
    
    def place_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        quantity: float,
        order_type: str = "MARKET"
    ) -> Optional[Dict]:
        """
        주문 실행
        
        Returns:
            {
                "order_id": str,
                "symbol": str,
                "side": str,
                "quantity": float,
                "filled_price": float,
                "status": str
            }
        """
        try:
            if self.dry_run:
                # 모의 거래
                logger.info(f"[DRY RUN] 주문: {side} {quantity} {symbol}")
                
                # 현재가 조회 (실제로는 API에서 가져옴)
                from data.data_fetcher import DataFetcher
                fetcher = DataFetcher()
                current_price = fetcher.get_realtime_price(symbol)
                
                if current_price is None:
                    logger.error(f"{symbol} 가격 조회 실패")
                    return None
                
                return {
                    "order_id": f"DRY_{symbol}_{side}",
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "filled_price": current_price,
                    "status": "FILLED"
                }
            
            # 실제 주문 실행
            # order = self.api.submit_order(
            #     symbol=symbol,
            #     qty=quantity,
            #     side=side.lower(),
            #     type=order_type.lower(),
            #     time_in_force="day"
            # )
            # 
            # return {
            #     "order_id": order.id,
            #     "symbol": symbol,
            #     "side": side,
            #     "quantity": quantity,
            #     "filled_price": order.filled_avg_price,
            #     "status": order.status
            # }
            
            logger.warning("실제 거래 API 미구현")
            return None
            
        except Exception as e:
            logger.error(f"주문 실행 실패: {e}")
            return None
    
    def open_long_position(self, symbol: str, price: float) -> Optional[Position]:
        """롱 포지션 오픈"""
        quantity = self.calculate_position_size(price)
        
        if quantity == 0:
            return None
        
        order = self.place_order(symbol, "BUY", quantity)
        
        if order is None or order["status"] != "FILLED":
            logger.error(f"{symbol} 롱 포지션 오픈 실패")
            return None
        
        filled_price = order["filled_price"]
        position = self.position_manager.open_position(
            symbol=symbol,
            side="LONG",
            entry_price=filled_price,
            quantity=quantity
        )
        
        if position:
            trade_amount = filled_price * quantity
            self.available_capital -= trade_amount
            logger.info(f"롱 포지션 오픈 성공: {symbol} @ ${filled_price:.2f}")
        
        return position
    
    def open_short_position(self, symbol: str, price: float) -> Optional[Position]:
        """숏 포지션 오픈"""
        quantity = self.calculate_position_size(price)
        
        if quantity == 0:
            return None
        
        order = self.place_order(symbol, "SELL", quantity)
        
        if order is None or order["status"] != "FILLED":
            logger.error(f"{symbol} 숏 포지션 오픈 실패")
            return None
        
        filled_price = order["filled_price"]
        position = self.position_manager.open_position(
            symbol=symbol,
            side="SHORT",
            entry_price=filled_price,
            quantity=quantity
        )
        
        if position:
            trade_amount = filled_price * quantity
            self.available_capital -= trade_amount
            logger.info(f"숏 포지션 오픈 성공: {symbol} @ ${filled_price:.2f}")
        
        return position
    
    def close_position(self, symbol: str) -> Optional[Position]:
        """포지션 청산"""
        position = self.position_manager.get_position(symbol)
        
        if position is None:
            return None
        
        order = self.place_order(
            symbol=symbol,
            side="SELL" if position.side == "LONG" else "BUY",
            quantity=position.quantity
        )
        
        if order is None or order["status"] != "FILLED":
            logger.error(f"{symbol} 포지션 청산 실패")
            return None
        
        closed_position = self.position_manager.close_position(symbol)
        
        if closed_position:
            # 자본 복원 (손익 반영)
            pnl = closed_position.get_pnl_amount()
            trade_amount = closed_position.entry_price * closed_position.quantity
            self.available_capital += trade_amount + pnl
            
            logger.info(
                f"포지션 청산 성공: {symbol} "
                f"손익: ${pnl:.2f} ({closed_position.get_pnl_pct():.2f}%)"
            )
        
        return closed_position

