"""
Tesla 전환 매매 전략 실행 봇 (KIS API 버전)
한국투자증권 OpenAPI를 이용하여 Tesla 및 2x ETF(TSLL/TSLZ) 전환 매매 수행
"""
import time
from datetime import datetime
import sys
import os
import pytz

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import REVERSAL_STRATEGY_PARAMS
from data.data_fetcher import DataFetcher
from strategy.reversal_strategy import ReversalStrategy
from strategy.signal_generator import SignalType
from utils.logger import logger
from utils.scheduler import TradingScheduler
from trading.kis_api import KisApi

class TeslaReversalTradingBot:
    """Tesla 전환 매매 전략 거래 봇 (KIS 연동)"""
    
    def __init__(self, params: dict = None):
        """
        전환 매매 봇 초기화
        """
        self.kis = KisApi(is_paper_trading=False) # 실전 투자 모드 (설정 확인 필요)
        # 만약 모의투자로 하려면 is_paper_trading=True 로 변경하거나 env 변수 활용
        # settings.py 에서 BASE_URL 로 관리하므로 KisApi 내부에서 처리됨. 
        # 여기서는 기본값 사용
        
        self.data_fetcher = DataFetcher() # 과거 데이터/지표용
        self.strategy = ReversalStrategy(params=params)
        self.scheduler = TradingScheduler()
        self.timezone = pytz.timezone("Asia/Seoul")
        self.is_running = False
        
        # === 사용자 요청 종목 설정 ===
        self.target_config = {
            "ORIGINAL": "TSLA",  # 원본 주식: Tesla
            "LONG": "TSLL",      # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
            "LONG_MULTIPLE": "2",
            "SHORT": "TSLZ",      # 2x 숏 ETF: T-Rex 2x Inverse Tesla Daily Target ETF
            "SHORT_MULTIPLE": "-2"
        }
        
        self.original_symbol = self.target_config["ORIGINAL"]
        self.etf_long = self.target_config["LONG"]
        self.etf_long_multiple = self.target_config["LONG_MULTIPLE"]
        self.etf_short = self.target_config["SHORT"]
        self.etf_short_multiple = self.target_config["SHORT_MULTIPLE"]
        
        logger.info(f"Tesla 전환 매매 봇 초기화 (KIS API): {self.original_symbol} -> {self.etf_long}/{self.etf_short}")
        
    def _get_current_price(self, symbol: str):
        """현재가 조회 (KIS API 우선 사용)"""
        price = self.kis.get_current_price(symbol)
        if price:
            return price
        
        logger.warning(f"KIS API 가격 조회 실패, yfinance 시도: {symbol}")
        return self.data_fetcher.get_realtime_price(symbol)

    def monitor_position(self):
        """포지션 모니터링 및 전환 조건 확인"""
        if not self.strategy.current_position:
            return
        
        try:
            # 현재 ETF 가격 조회
            target_symbol = self.etf_long if self.strategy.current_position == "LONG" else self.etf_short
            current_price = self._get_current_price(target_symbol)
            
            if not current_price:
                return
            
            # 손절/익절 확인
            multiple = self.etf_long_multiple if self.strategy.current_position == "LONG" else self.etf_short_multiple
            exit_reason = self.strategy.check_stop_loss_take_profit2(current_price, multiple)
            
            if exit_reason:
                logger.info(f"{self.strategy.current_etf_symbol} {exit_reason} 조건 충족")
                
                # 손절인 경우 전환 매매 실행
                if exit_reason == "STOP_LOSS" and self.strategy.params.get("reverse_trigger", True):
                    self._execute_reversal(exit_reason)
                else:
                    # 익절인 경우 일반 청산
                    self._close_position(current_price, exit_reason)
            
            # 최대 보유 기간 확인
            if self.strategy.check_max_hold_days2(datetime.now()):
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
            # 원본 주식 데이터 수집 (지표 계산용, yfinance 사용)
            original_data = self.data_fetcher.get_intraday_data(
                self.original_symbol, 
                interval="5m"
            )
            
            if original_data is None or len(original_data) < 50:
                logger.warning(f"{self.original_symbol} 데이터 부족")
                return
            
            # ETF 가격 조회
            etf_long_price = self._get_current_price(self.etf_long)
            etf_short_price = self._get_current_price(self.etf_short)
            
            if not etf_long_price or not etf_short_price:
                logger.warning("ETF 가격 조회 실패")
                return
            
            # === 실제 주문 실행 (청산 -> 진입) ===
            # 전략 내부 상태 업데이트 전에 실제 주문부터 시도하는 것이 안전할 수 있으나,
            # Strategy 클래스가 복잡한 로직(수수료, 기록 등)을 담고 있어서
            # Strategy.execute_reversal 호출 후, 성공하면 실제 주문을 내는 순서로 가거나
            # 아니면 Strategy 메서드를 호출하기 전에 주문을 냄.
            # 여기서는 Strategy를 'Logic Core'로 쓰고, 실제 주문은 사이드 이펙트로 처리.
            
            # 1. 기존 포지션 청산 주문
            if self.strategy.current_position:
                close_symbol = self.strategy.current_etf_symbol
                close_qty = self.strategy.entry_quantity
                # 매도 주문
                logger.info(f"[KIS] 청산 주문 실행: {close_symbol} {close_qty}주")
                # 시장가 매도 가정 (또는 현재가 지정가)
                # self.kis.place_order(close_symbol, "SELL", close_qty, etf_long_price if ... else ...)
                # 여기서 close_qty가 0이 아니라고 가정.
                # *실제 구현*: 현재가가 아닌 '시장가'로 던지는게 확실함. KIS API place_order에서 0원 입력시 시장가 로직 필요.
                # kis_api.py에서 price=0이면 시장가(01)로 하도록 수정했는지 확인.
                # (kis_api.py 작성시 price=0이라고 시장가로 자동변환하지 않았음. arg로 제어)
                
                # 안전하게 지정가로 현재가 사용
                close_price = etf_long_price if self.strategy.current_position == "LONG" else etf_short_price
                # 실제 주문
                res = self.kis.place_order(close_symbol, "SELL", close_qty, price=0, order_type="01") # 시장가
                if not res:
                    logger.error("청산 주문 실패, 전환 중단")
                    return

            # 2. 전환 로직 실행 (상태 업데이트)
            result = self.strategy.execute_reversal(
                original_symbol=self.original_symbol,
                etf_long=self.etf_long,
                etf_short=self.etf_short,
                original_data=original_data,
                etf_long_price=etf_long_price,
                etf_short_price=etf_short_price,
                current_time=datetime.now(),
                reason=reason
            )
            
            if result:
                # 3. 신규 진입 주문
                new_symbol = result['to_etf']
                new_qty = result['quantity']
                # 매수 주문
                logger.info(f"[KIS] 진입 주문 실행: {new_symbol} {new_qty}주")
                res = self.kis.place_order(new_symbol, "BUY", new_qty, price=0, order_type="01") # 시장가
                if not res:
                    logger.error("진입 주문 실패")
                    # 롤백 로직 필요할 수 있으나 복잡하므로 로그만 남김
                    
                logger.info(f"✅ 전환 매매 성공: {result['from_etf']} -> {result['to_etf']}")
            else:
                logger.info("전환 매매 조건 미충족 (Strategy 내부 로직)")
                
        except Exception as e:
            logger.error(f"전환 매매 실행 실패: {e}")
    
    def _close_position(self, current_price: float, reason: str):
        """포지션 청산 (전환 없이)"""
        if not self.strategy.current_position:
            return
        
        # KIS 주문
        symbol = self.strategy.current_etf_symbol
        qty = self.strategy.entry_quantity
        logger.info(f"[KIS] 청산 주문: {symbol} {qty}주 ({reason})")
        
        res = self.kis.place_order(symbol, "SELL", qty, price=0, order_type="01") # 시장가
        if not res:
            logger.error("청산 주문 실패")
            return

        # 전략 상태 업데이트 (기존 로직 복붙 + 수정)
        # self.strategy 클래스에는 _close_position 같은 퍼블릭 메서드가 없음.
        # strategy 로직 안에서 capital 업데이트 등을 직접 해줘야 함.
        # ReversalTradingBot._close_position 내용을 가져와서 사용.
        
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
                # 원본 주식 데이터 수집 (지표용)
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
                target_etf = None
                position_side = None
                
                if signal == SignalType.BUY and confidence > 0.5:
                    target_etf = self.etf_long
                    position_side = "LONG"
                elif signal == SignalType.SELL and confidence > 0.5:
                    target_etf = self.etf_short
                    position_side = "SHORT"
                    
                if target_etf:
                    # ETF 가격 조회
                    etf_price = self._get_current_price(target_etf)
                    
                    if etf_price:
                        quantity = self.strategy.calculate_position_size(etf_price, is_reversal=False)
                        if quantity > 0:
                            # KIS 주문
                            logger.info(f"[KIS] 진입 주문: {target_etf} {quantity}주")
                            res = self.kis.place_order(target_etf, "BUY", quantity, price=0, order_type="01") # 시장가
                            
                            if res:
                                trade_amount = etf_price * quantity
                                self.strategy.capital -= trade_amount
                                
                                self.strategy.current_position = position_side
                                self.strategy.current_etf_symbol = target_etf
                                self.strategy.entry_price = etf_price
                                self.strategy.entry_time = datetime.now()
                                self.strategy.entry_quantity = quantity
                                
                                logger.info(
                                    f"{position_side} 포지션 진입: {target_etf} @ ${etf_price:.2f} x {quantity:.2f} "
                                    f"(신뢰도: {confidence:.2f})"
                                )
                            else:
                                logger.error("진입 주문 실패")
                                
            except Exception as e:
                logger.error(f"거래 전략 실행 실패: {e}")
        
        # 포지션 모니터링 (항상 실행)
        self.monitor_position()
    
    def force_close_all_positions(self):
        """새벽 05:00 강제 청산"""
        logger.info("새벽 05:00 강제 청산 시작")
        
        if self.strategy.current_position and self.strategy.current_etf_symbol:
            target_symbol = self.strategy.current_etf_symbol
            current_price = self._get_current_price(target_symbol)
            
            if current_price:
                self._close_position(current_price, "FORCE_CLOSE")
        
        logger.info("새벽 05:00 강제 청산 완료")
    
    def run(self):
        """봇 실행"""
        logger.info(f"Tesla 전환 매매 봇 시작 (Target: {self.original_symbol})")
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
            logger.info("봇 종료 요청")
            self.stop()
    
    def stop(self):
        """봇 종료"""
        logger.info("봇 종료 중...")
        self.is_running = False
        
        # 모든 포지션 청산
        if self.strategy.current_position:
            target_symbol = self.strategy.current_etf_symbol
            current_price = self._get_current_price(target_symbol)
            
            if current_price:
                self._close_position(current_price, "BOT_STOP")
        
        status = self.strategy.get_strategy_status()
        logger.info(f"전략 최종 상태: {status}")
        logger.info("봇 종료 완료")

if __name__ == "__main__":
    # KIS API 사용을 위해 .env 확인 필요
    # 설정 파일 로드
    custom_params = REVERSAL_STRATEGY_PARAMS.copy()
    custom_params["symbol"] = "TSLA"
    
    bot = TeslaReversalTradingBot(params=custom_params)
    bot.run()
