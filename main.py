"""
메인 거래 봇 실행 파일
"""
import time
from datetime import datetime
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, INITIAL_CAPITAL_MIN
from data.data_fetcher import DataFetcher
from strategy.signal_generator import SignalGenerator, SignalType
from trading.trader import Trader
from trading.position_manager import PositionManager
from utils.logger import logger
from utils.scheduler import TradingScheduler

class TradingBot:
    """메인 거래 봇 클래스"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.signal_generator = SignalGenerator()
        self.trader = Trader(initial_capital=INITIAL_CAPITAL_MIN)
        self.scheduler = TradingScheduler()
        self.is_running = False
        
        logger.info("거래 봇 초기화 완료")
    
    def monitor_positions(self):
        """포지션 모니터링 및 자동 청산"""
        positions = self.trader.position_manager.get_all_positions()
        
        for symbol, position in positions.items():
            # 현재가 업데이트
            current_price = self.data_fetcher.get_realtime_price(symbol)
            if current_price:
                self.trader.position_manager.update_position_price(symbol, current_price)
            
            # 청산 조건 확인
            exit_reason = self.trader.position_manager.check_exit_conditions(symbol)
            
            if exit_reason:
                logger.info(f"{symbol} 청산 조건 충족: {exit_reason}")
                self.trader.close_position(symbol)
    
    def execute_trading_strategy(self):
        """거래 전략 실행"""
        if not self.scheduler.is_within_trading_hours():
            logger.debug("거래 시간 아님")
            return
        
        for symbol in TARGET_SYMBOLS:
            try:
                # 현재 포지션 확인
                current_position = None
                position = self.trader.position_manager.get_position(symbol)
                if position:
                    current_position = position.side
                
                # 데이터 수집
                data = self.data_fetcher.get_intraday_data(symbol, interval="5m")
                if data is None or len(data) < 50:
                    logger.warning(f"{symbol} 데이터 부족")
                    continue
                
                # 매매 신호 생성
                signal_data = self.signal_generator.generate_signal(
                    data, current_position
                )
                
                signal = signal_data["signal"]
                confidence = signal_data["confidence"]
                reason = signal_data["reason"]
                
                logger.info(
                    f"{symbol} 신호: {signal.value}, "
                    f"신뢰도: {confidence:.2f}, 이유: {reason}"
                )
                
                # 신호에 따른 거래 실행
                if signal == SignalType.BUY and current_position != "LONG":
                    if current_position == "SHORT":
                        # 반대 포지션 청산 후 롱 진입
                        self.trader.close_position(symbol)
                    
                    current_price = self.data_fetcher.get_realtime_price(symbol)
                    if current_price and confidence > 0.5:
                        self.trader.open_long_position(symbol, current_price)
                
                elif signal == SignalType.SELL and current_position != "SHORT":
                    if current_position == "LONG":
                        # 반대 포지션 청산 후 숏 진입
                        self.trader.close_position(symbol)
                    
                    current_price = self.data_fetcher.get_realtime_price(symbol)
                    if current_price and confidence > 0.5:
                        self.trader.open_short_position(symbol, current_price)
                
                # 포지션 모니터링
                self.monitor_positions()
                
            except Exception as e:
                logger.error(f"{symbol} 거래 전략 실행 실패: {e}")
    
    def run(self):
        """봇 실행"""
        logger.info("거래 봇 시작")
        self.is_running = True
        
        # 스케줄러 설정
        self.scheduler.schedule_daily_tasks(
            self.execute_trading_strategy,
            self.monitor_positions
        )
        
        # 메인 루프
        try:
            while self.is_running:
                self.scheduler.run()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("거래 봇 종료 요청")
            self.stop()
    
    def stop(self):
        """봇 종료"""
        logger.info("거래 봇 종료 중...")
        self.is_running = False
        
        # 모든 포지션 청산
        positions = self.trader.position_manager.get_all_positions()
        for symbol in positions.keys():
            self.trader.close_position(symbol)
        
        logger.info("거래 봇 종료 완료")

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()

