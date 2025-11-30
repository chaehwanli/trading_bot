"""
전환 매매 전략 실행 봇
Reverse/Flip Trading Strategy를 사용하는 거래 봇
"""
import time
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, get_etf_by_original, REVERSAL_STRATEGY_PARAMS
from data.data_fetcher import DataFetcher
from strategy.reversal_strategy import ReversalStrategy
from strategy.signal_generator import SignalType
from utils.logger import logger
from utils.scheduler import TradingScheduler
import pytz

class ReversalTradingBot:
    """전환 매매 전략 거래 봇"""
    
    def __init__(self, params: dict = None):
        """
        전환 매매 봇 초기화
        
        Args:
            params: 전략 파라미터 (None이면 설정 파일 값 사용)
        """
        self.data_fetcher = DataFetcher()
        self.strategy = ReversalStrategy(params=params)
        self.scheduler = TradingScheduler()
        self.timezone = pytz.timezone("Asia/Seoul")
        self.is_running = False
        
        # 거래 대상 설정
        self.original_symbol = self.strategy.params.get("symbol", "TSLA")
        etf_info = get_etf_by_original(self.original_symbol)
        if not etf_info:
            raise ValueError(f"{self.original_symbol}에 해당하는 ETF 정보를 찾을 수 없습니다")
        
        self.etf_long = etf_info["LONG"]
        self.etf_short = etf_info["SHORT"]
        
        logger.info(f"전환 매매 봇 초기화: {self.original_symbol} -> {self.etf_long}/{self.etf_short}")
    
    def monitor_position(self):
        """포지션 모니터링 및 전환 조건 확인"""
        if not self.strategy.current_position:
            return
        
        try:
            # 현재 ETF 가격 조회
            if self.strategy.current_position == "LONG":
                current_price = self.data_fetcher.get_realtime_price(self.etf_long)
            else:
                current_price = self.data_fetcher.get_realtime_price(self.etf_short)
            
            if not current_price:
                return
            
            # 손절/익절 확인
            exit_reason = self.strategy.check_stop_loss_take_profit(current_price)
            
            if exit_reason:
                logger.info(f"{self.strategy.current_etf_symbol} {exit_reason} 조건 충족")
                
                # 손절인 경우 전환 매매 실행
                if exit_reason == "STOP_LOSS" and self.strategy.params.get("reverse_trigger", True):
                    self._execute_reversal(exit_reason)
                else:
                    # 익절인 경우 일반 청산
                    self._close_position(current_price, exit_reason)
            
            # 최대 보유 기간 확인
            if self.strategy.check_max_hold_days():
                self._close_position(current_price, "FORCE_CLOSE")
            
            # 최대 자본 손실률 확인
            if self.strategy.check_max_drawdown():
                logger.error("최대 자본 손실률 초과 - 거래 중단")
                self.stop()
                
        except Exception as e:
            logger.error(f"포지션 모니터링 실패: {e}")
    
    def _execute_reversal(self, reason: str = "손절 전환"):
        """전환 매매 실행"""
        try:
            # 원본 주식 데이터 수집
            original_data = self.data_fetcher.get_intraday_data(
                self.original_symbol, 
                interval="5m"
            )
            
            if original_data is None or len(original_data) < 50:
                logger.warning(f"{self.original_symbol} 데이터 부족")
                return
            
            # ETF 가격 조회
            etf_long_price = self.data_fetcher.get_realtime_price(self.etf_long)
            etf_short_price = self.data_fetcher.get_realtime_price(self.etf_short)
            
            if not etf_long_price or not etf_short_price:
                logger.warning("ETF 가격 조회 실패")
                return
            
            # 전환 매매 실행
            result = self.strategy.execute_reversal(
                original_symbol=self.original_symbol,
                etf_long=self.etf_long,
                etf_short=self.etf_short,
                original_data=original_data,
                etf_long_price=etf_long_price,
                etf_short_price=etf_short_price,
                reason=reason
            )
            
            if result:
                logger.info(f"✅ 전환 매매 성공: {result['from_etf']} -> {result['to_etf']}")
            else:
                logger.info("전환 매매 조건 미충족")
                
        except Exception as e:
            logger.error(f"전환 매매 실행 실패: {e}")
    
    def _close_position(self, current_price: float, reason: str):
        """포지션 청산 (전환 없이)"""
        if not self.strategy.current_position or not self.strategy.entry_price:
            return
        
        if self.strategy.current_position == "LONG":
            pnl_pct = ((current_price - self.strategy.entry_price) / self.strategy.entry_price) * 100
        else:
            pnl_pct = ((self.strategy.entry_price - current_price) / self.strategy.entry_price) * 100
        
        pnl = self.strategy.entry_quantity * self.strategy.entry_price * (pnl_pct / 100)
        self.strategy.capital += self.strategy.entry_quantity * self.strategy.entry_price + pnl
        
        trade_record = {
            'entry_time': self.strategy.entry_time,
            'exit_time': datetime.now(),
            'symbol': self.strategy.current_etf_symbol,
            'side': self.strategy.current_position,
            'entry_price': self.strategy.entry_price,
            'exit_price': current_price,
            'quantity': self.strategy.entry_quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        }
        self.strategy.trade_history.append(trade_record)
        
        logger.info(
            f"포지션 청산: {self.strategy.current_etf_symbol} {self.strategy.current_position} "
            f"@ ${current_price:.2f} (손익: {pnl_pct:.2f}%) - {reason}"
        )
        
        # 포지션 초기화
        self.strategy.current_position = None
        self.strategy.current_etf_symbol = None
        self.strategy.entry_price = None
        self.strategy.entry_time = None
        self.strategy.entry_quantity = None
    
    def execute_trading_strategy(self):
        """거래 전략 실행 (17:00~18:00)"""
        now = datetime.now(self.timezone)
        current_hour = now.hour
        
        # 17:00~18:00: 종목선정 및 진입
        if 17 <= current_hour < 18:
            logger.info("전환 매매 전략 실행 시간 (17:00~18:00)")
            
            # 이미 포지션이 있으면 스킵
            if self.strategy.current_position:
                logger.info(f"이미 포지션 보유 중: {self.strategy.current_etf_symbol} {self.strategy.current_position}")
                return
            
            try:
                # 원본 주식 데이터 수집
                original_data = self.data_fetcher.get_intraday_data(
                    self.original_symbol,
                    interval="5m"
                )
                
                if original_data is None or len(original_data) < 50:
                    logger.warning(f"{self.original_symbol} 데이터 부족")
                    return
                
                # 신호 생성
                signal_data = self.strategy.signal_generator.generate_signal(
                    original_data,
                    None
                )
                
                signal = signal_data["signal"]
                confidence = signal_data["confidence"]
                
                # 진입 조건 확인
                if signal == SignalType.BUY and confidence > 0.5:
                    # 롱 ETF 진입
                    etf_price = self.data_fetcher.get_realtime_price(self.etf_long)
                    if etf_price:
                        quantity = self.strategy.calculate_position_size(etf_price, is_reversal=False)
                        if quantity > 0:
                            trade_amount = etf_price * quantity
                            self.strategy.capital -= trade_amount
                            
                            self.strategy.current_position = "LONG"
                            self.strategy.current_etf_symbol = self.etf_long
                            self.strategy.entry_price = etf_price
                            self.strategy.entry_time = datetime.now()
                            self.strategy.entry_quantity = quantity
                            
                            logger.info(
                                f"롱 포지션 진입: {self.etf_long} @ ${etf_price:.2f} x {quantity:.2f} "
                                f"(신뢰도: {confidence:.2f})"
                            )
                
                elif signal == SignalType.SELL and confidence > 0.5:
                    # 숏 ETF 진입
                    etf_price = self.data_fetcher.get_realtime_price(self.etf_short)
                    if etf_price:
                        quantity = self.strategy.calculate_position_size(etf_price, is_reversal=False)
                        if quantity > 0:
                            trade_amount = etf_price * quantity
                            self.strategy.capital -= trade_amount
                            
                            self.strategy.current_position = "SHORT"
                            self.strategy.current_etf_symbol = self.etf_short
                            self.strategy.entry_price = etf_price
                            self.strategy.entry_time = datetime.now()
                            self.strategy.entry_quantity = quantity
                            
                            logger.info(
                                f"숏 포지션 진입: {self.etf_short} @ ${etf_price:.2f} x {quantity:.2f} "
                                f"(신뢰도: {confidence:.2f})"
                            )
                            
            except Exception as e:
                logger.error(f"거래 전략 실행 실패: {e}")
        
        # 포지션 모니터링 (항상 실행)
        self.monitor_position()
    
    def force_close_all_positions(self):
        """새벽 05:00 강제 청산"""
        logger.info("새벽 05:00 강제 청산 시작")
        
        if self.strategy.current_position and self.strategy.current_etf_symbol:
            if self.strategy.current_position == "LONG":
                current_price = self.data_fetcher.get_realtime_price(self.etf_long)
            else:
                current_price = self.data_fetcher.get_realtime_price(self.etf_short)
            
            if current_price:
                self._close_position(current_price, "FORCE_CLOSE")
        
        logger.info("새벽 05:00 강제 청산 완료")
    
    def run(self):
        """봇 실행"""
        logger.info("전환 매매 봇 시작")
        self.is_running = True
        
        # 스케줄러 설정
        self.scheduler.schedule_daily_tasks(
            self.execute_trading_strategy,
            self.monitor_position,
            self.force_close_all_positions
        )
        
        # 메인 루프
        try:
            while self.is_running:
                self.scheduler.run()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("전환 매매 봇 종료 요청")
            self.stop()
    
    def stop(self):
        """봇 종료"""
        logger.info("전환 매매 봇 종료 중...")
        self.is_running = False
        
        # 모든 포지션 청산
        if self.strategy.current_position and self.strategy.current_etf_symbol:
            if self.strategy.current_position == "LONG":
                current_price = self.data_fetcher.get_realtime_price(self.etf_long)
            else:
                current_price = self.data_fetcher.get_realtime_price(self.etf_short)
            
            if current_price:
                self._close_position(current_price, "BOT_STOP")
        
        # 전략 상태 출력
        status = self.strategy.get_strategy_status()
        logger.info(f"전략 최종 상태: {status}")
        logger.info("전환 매매 봇 종료 완료")
    
    def get_status(self) -> dict:
        """봇 상태 조회"""
        return self.strategy.get_strategy_status()

if __name__ == "__main__":
    # 커스텀 파라미터 사용 예시
    custom_params = REVERSAL_STRATEGY_PARAMS.copy()
    custom_params["symbol"] = "TSLA"
    custom_params["capital"] = 2000
    custom_params["reverse_trigger"] = True
    custom_params["reverse_mode"] = "full"
    
    bot = ReversalTradingBot(params=custom_params)
    bot.run()

