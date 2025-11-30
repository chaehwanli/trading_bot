"""
메인 거래 봇 실행 파일
"""
import time
from datetime import datetime
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, INITIAL_CAPITAL_MIN, FORCE_CLOSE_HOUR, get_all_etf_symbols, get_etf_by_original
from data.data_fetcher import DataFetcher
from strategy.signal_generator import SignalGenerator, SignalType
from strategy.symbol_selector import SymbolSelector
from trading.trader import Trader
from trading.position_manager import PositionManager
from utils.logger import logger
from utils.scheduler import TradingScheduler
import pytz

class TradingBot:
    """메인 거래 봇 클래스"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.signal_generator = SignalGenerator()
        self.symbol_selector = SymbolSelector()
        self.trader = Trader(initial_capital=INITIAL_CAPITAL_MIN)
        self.scheduler = TradingScheduler()
        self.is_running = False
        self.timezone = pytz.timezone("Asia/Seoul")
        
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
                closed_position = self.trader.close_position(symbol)
                
                # 손절 발생 시 반대 포지션 검토
                if closed_position and exit_reason == "STOP_LOSS":
                    pnl_pct = closed_position.get_pnl_pct()
                    if pnl_pct < 0:  # 손실인 경우
                        logger.info(f"{symbol} 손절 발생, 반대 포지션 검토 시작")
                        self._consider_opposite_position(symbol, closed_position.side)
    
    def _consider_opposite_position(self, etf_symbol: str, previous_side: str):
        """손절 발생 시 반대 포지션 검토 및 진입"""
        try:
            # ETF 심볼로부터 원본 주식 찾기
            etf_info = get_etf_by_original(None)  # 임시로 None 전달
            original_symbol = None
            for item in TARGET_SYMBOLS:
                if item["LONG"] == etf_symbol or item["SHORT"] == etf_symbol:
                    original_symbol = item["ORIGINAL"]
                    etf_info = item
                    break
            
            if not original_symbol:
                logger.warning(f"{etf_symbol}에 해당하는 원본 주식을 찾을 수 없음")
                return
            
            opposite_side = "SHORT" if previous_side == "LONG" else "LONG"
            opposite_etf = etf_info["SHORT"] if opposite_side == "SHORT" else etf_info["LONG"]
            
            # 원본 주식 데이터 수집
            data = self.data_fetcher.get_intraday_data(original_symbol, interval="5m")
            if data is None or len(data) < 50:
                logger.warning(f"{original_symbol} 반대 포지션 검토 실패: 데이터 부족")
                return
            
            # 신호 생성
            signal_data = self.signal_generator.generate_signal(data, None)
            signal = signal_data["signal"]
            confidence = signal_data["confidence"]
            
            # 반대 포지션 진입 조건 확인
            should_enter = False
            if opposite_side == "LONG" and signal == SignalType.BUY and confidence > 0.5:
                should_enter = True
            elif opposite_side == "SHORT" and signal == SignalType.SELL and confidence > 0.5:
                should_enter = True
            
            if should_enter:
                current_price = self.data_fetcher.get_realtime_price(opposite_etf)
                if current_price:
                    if opposite_side == "LONG":
                        self.trader.open_long_position(opposite_etf, current_price)
                    else:
                        self.trader.open_short_position(opposite_etf, current_price)
                    logger.info(f"{original_symbol} -> {opposite_etf} 반대 포지션({opposite_side}) 진입 완료")
            else:
                logger.info(f"{original_symbol} -> {opposite_etf} 반대 포지션 진입 조건 미충족 (신호: {signal.value}, 신뢰도: {confidence:.2f})")
                
        except Exception as e:
            logger.error(f"{etf_symbol} 반대 포지션 검토 실패: {e}")
    
    def execute_trading_strategy(self):
        """거래 전략 실행 (17:00~18:00 종목선정 및 진입)"""
        now = datetime.now(self.timezone)
        current_hour = now.hour
        
        # 17:00~18:00: 종목선정 및 진입
        if 17 <= current_hour < 18:
            logger.info("종목선정 시간 (17:00~18:00)")
            
            # 전일 포지션 정보 수집
            previous_positions = {}
            positions = self.trader.position_manager.get_all_positions()
            for symbol, position in positions.items():
                # 전일 포지션인지 확인 (24시간 이상 보유)
                hold_duration = datetime.now() - position.entry_time
                if hold_duration.days >= 1:
                    previous_positions[symbol] = position.side
            
            # 종목선정
            selected_symbols = self.symbol_selector.select_symbols(
                previous_positions=previous_positions if previous_positions else None,
                max_symbols=3
            )
            
            # 선택된 종목에 대해 진입
            for item in selected_symbols:
                original_symbol = item["original"]  # 원본 주식 (예: "TSLA")
                etf_symbol = item["symbol"]         # 실제 거래할 ETF (예: "TSLL" 또는 "TSLZ")
                target_side = item["side"]          # "LONG" or "SHORT"
                
                try:
                    # 현재 포지션 확인 (ETF 심볼 기준)
                    current_position = None
                    position = self.trader.position_manager.get_position(etf_symbol)
                    if position:
                        current_position = position.side
                    
                    # 이미 목표 포지션이 있으면 스킵
                    if current_position == target_side:
                        logger.info(f"{original_symbol} -> {etf_symbol} 이미 {target_side} 포지션 보유 중")
                        continue
                    
                    # 반대 포지션이 있으면 청산
                    if current_position and current_position != target_side:
                        logger.info(f"{original_symbol} -> {etf_symbol} 반대 포지션({current_position}) 청산 후 {target_side} 진입")
                        self.trader.close_position(etf_symbol)
                    
                    # 원본 주식 데이터 수집 및 신호 확인
                    data = self.data_fetcher.get_intraday_data(original_symbol, interval="5m")
                    if data is None or len(data) < 50:
                        logger.warning(f"{original_symbol} 데이터 부족")
                        continue
                    
                    signal_data = self.signal_generator.generate_signal(data, None)
                    signal = signal_data["signal"]
                    confidence = signal_data["confidence"]
                    
                    # 진입 조건 확인
                    should_enter = False
                    if target_side == "LONG" and signal == SignalType.BUY and confidence > 0.5:
                        should_enter = True
                    elif target_side == "SHORT" and signal == SignalType.SELL and confidence > 0.5:
                        should_enter = True
                    
                    if should_enter:
                        # ETF 가격 조회
                        current_price = self.data_fetcher.get_realtime_price(etf_symbol)
                        if current_price:
                            if target_side == "LONG":
                                self.trader.open_long_position(etf_symbol, current_price)
                            else:
                                self.trader.open_short_position(etf_symbol, current_price)
                            logger.info(f"{original_symbol} -> {etf_symbol} {target_side} 포지션 진입 완료")
                    else:
                        logger.info(f"{original_symbol} -> {etf_symbol} {target_side} 진입 조건 미충족 (신호: {signal.value}, 신뢰도: {confidence:.2f})")
                        
                except Exception as e:
                    logger.error(f"{original_symbol} -> {etf_symbol} 거래 전략 실행 실패: {e}")
        
        # 기존 포지션 모니터링 (항상 실행)
        self.monitor_positions()
    
    def force_close_all_positions(self):
        """새벽 05:00 강제 청산 - 모든 오픈 포지션 청산"""
        logger.info("새벽 05:00 강제 청산 시작")
        positions = self.trader.position_manager.get_all_positions()
        
        if not positions:
            logger.info("청산할 포지션 없음")
            return
        
        for symbol, position in positions.items():
            try:
                logger.info(f"{symbol} {position.side} 포지션 강제 청산")
                self.trader.close_position(symbol)
            except Exception as e:
                logger.error(f"{symbol} 강제 청산 실패: {e}")
        
        logger.info("새벽 05:00 강제 청산 완료")
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
            self.monitor_positions,
            self.force_close_all_positions
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

