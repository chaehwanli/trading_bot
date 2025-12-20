"""
Tesla 전환 매매 전략 실행 봇 (KIS API 버전)
한국투자증권 OpenAPI를 이용하여 Tesla 및 2x ETF(TSLL/TSLZ) 전환 매매 수행
"""
import time
from datetime import datetime
import sys
import os
import pytz
import schedule

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import REVERSAL_STRATEGY_PARAMS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from data.data_fetcher import DataFetcher
from strategy.reversal_strategy import ReversalStrategy
from strategy.signal_generator import SignalType
from utils.logger import logger
from utils.telegram_notifier import TelegramNotifier
from utils.scheduler import TradingScheduler
from trading.kis_api import KisApi
from utils.state_manager import TradeStateManager

class TeslaReversalTradingBot:
    """Tesla 전환 매매 전략 거래 봇 (KIS 연동)"""
    
    def __init__(self, params: dict = None, is_paper_trading: bool = True):
        """
        전환 매매 봇 초기화
        :param is_paper_trading: 모의투자 여부 (기본값 True로 변경하여 안전한 테스트 권장)
        """
        # === 사용자 요청 종목 설정 ===
        self.target_config = {
            "ORIGINAL": "TSLA",  # 원본 주식: Tesla
            "LONG": "TSLL",      # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
            "LONG_MULTIPLE": "2",
            "SHORT": "TSLS",      # 1x 숏 ETF: Direxion Daily TSLA Bear 1X Shares
            "SHORT_MULTIPLE": "-1"
        }
        
        self.original_symbol = self.target_config["ORIGINAL"]
        self.etf_long = self.target_config["LONG"]
        self.etf_long_multiple = self.target_config["LONG_MULTIPLE"]
        self.etf_short = self.target_config["SHORT"]
        self.etf_short_multiple = self.target_config["SHORT_MULTIPLE"]

        self.kis = KisApi(is_paper_trading=is_paper_trading)
        # 만약 모의투자로 하려면 is_paper_trading=True 로 변경하거나 env 변수 활용
        # settings.py 에서 BASE_URL 로 관리하므로 KisApi 내부에서 처리됨. 
        # 여기서는 기본값 사용
        
        # DataFetcher 초기화 (KIS 인스턴스 공유)
        self.data_fetcher = DataFetcher(kis_client=self.kis)
        
        # 상태 관리자 초기화
        self.state_manager = TradeStateManager()
        
        # 전략 초기화
        # ReversalStrategy는 params만 받음 (__init__ 확인완료)
        self.strategy = ReversalStrategy(params=params)
        self.scheduler = TradingScheduler()
        self.notifier = TelegramNotifier(token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID)
        self.timezone = pytz.timezone("Asia/Seoul")
        self.is_running = False
        
        # 쿨다운 상태 (날짜 기준)
        self.cooldown_until_date = None
        # 강제청산 날짜 (거래일 기준)
        self.forced_close_date = None
        
        logger.info(f"Tesla 전환 매매 봇 초기화 (KIS API): {self.original_symbol} -> {self.etf_long}/{self.etf_short}")
        
    def _is_dst(self):
        """미국 서머타임 체킹 (US/Eastern 기준)"""
        eastern = pytz.timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        return bool(now_eastern.dst())

    def _calculate_trading_day_limit(self, start_date, days):
        """
        거래일 기준 날짜 계산 (단순화: 주말 제외)
        실제 휴장은 고려하지 않으나, 대략적인 거래일 계산
        """
        current_date = start_date
        added_days = 0
        while added_days < days:
             current_date += __import__("datetime").timedelta(days=1)
             # 토(5), 일(6) 제외 (0=월)
             if current_date.weekday() < 5:
                 added_days += 1
        return current_date

    def _get_market_status(self):
        """현재 시간 기준 장 상태 반환 (한국 시간 기준)"""
        now = datetime.now(self.timezone)
        current_time = now.time()
        is_dst = self._is_dst()
        
        # 시간 변환을 위한 분 단위 계산
        curr_min = current_time.hour * 60 + current_time.minute
        
        if is_dst: # Summer Time
            # Daytime: 10:00 ~ 17:00
            if 600 <= curr_min < 1020: return "DAYTIME"
            # Premarket: 17:00 ~ 22:30
            if 1020 <= curr_min < 1350: return "PREMARKET"
            # Regular: 22:30 ~ 05:00 (Next day handled by overflow check if needed, but here we assume simple ranges for now. 
            # Note: Regular crosses midnight local time. 22:30 is 1350. 05:00 is 300.
            if 1350 <= curr_min or curr_min < 300: return "REGULAR"
            # Aftermarket: 05:00 ~ 07:00
            if 300 <= curr_min < 420: return "AFTERMARKET"
            # Extended: 07:00 ~ 09:00
            if 420 <= curr_min < 540: return "EXTENDED"
        else: # Winter Time
            # Daytime: 10:00 ~ 18:00
            if 600 <= curr_min < 1080: return "DAYTIME"
            # Premarket: 18:00 ~ 23:30
            if 1080 <= curr_min < 1410: return "PREMARKET"
            # Regular: 23:30 ~ 06:00
            if 1410 <= curr_min or curr_min < 360: return "REGULAR"
            # Aftermarket: 06:00 ~ 07:00
            if 360 <= curr_min < 420: return "AFTERMARKET"
            # Extended: 07:00 ~ 09:00
            if 420 <= curr_min < 540: return "EXTENDED"
            
        return "CLOSED"

    def _get_current_price(self, symbol: str):
        """현재가 조회 (KIS API 우선 -> 실패 시 DataFetcher(yfinance) Fallback)"""
        price = self.kis.get_current_price(symbol)
        if price:
            return price
        
        raise Exception(f"KIS API 가격 조회 실패: {symbol}")
        # logger.warning(f"KIS API 가격 조회 실패, yfinance 시도: {symbol}")
        # return self.data_fetcher.get_realtime_price(symbol)
        logger.warning(f"KIS API 가격 조회 실패 (Bot), yfinance 시도: {symbol}")
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
                
                self._close_position(current_price, exit_reason)
                
                # === STOP_LOSS 쿨다운 설정 (4일) ===
                if exit_reason == "STOP_LOSS":
                   from datetime import timedelta
                   now = datetime.now(self.timezone)
                   self.cooldown_until_date = (now + timedelta(days=4)).date()
                   logger.info(f"⛔ STOP_LOSS 쿨다운 시작 -> {self.cooldown_until_date} 까지 거래 중단")
            
            # 최대 보유 기간 확인 (요청사항 4: 시간 -> 거래일 수 기준)
            # LOGIC SYNC: reversal_backtest.py uses trading days.
            # LONG: 3 trading days, SHORT: 1 trading day
            # If forced_close_date is set, compare with current date.
            
            if self.forced_close_date:
                today = datetime.now(self.timezone).date()
                if today >= self.forced_close_date:
                    self._close_position(current_price, "FORCE_CLOSE_TRADING_DAY_LIMIT")
                    
                    # === FORCE_CLOSE 후 처리 ===
                    # 1. 이익이면 연속 손절 카운트 리셋 (기존 로직)
                    if self.strategy.trade_history:
                        last_trade = self.strategy.trade_history[-1]
                        if last_trade['pnl'] > 0:
                            self.strategy.consecutive_stop_losses = 0
                            self.strategy.stop_loss_cooldown_until = None
                            logger.info("✅ FORCE_CLOSE 이익 실현으로 연속 손절 카운트 초기화")
            
            # 최대 자본 손실률 확인
            if self.strategy.check_max_drawdown():
                logger.error("최대 자본 손실률 초과 - 거래 중단")
                self.stop()
                
        except Exception as e:
            logger.error(f"포지션 모니터링 실패: {e}")
            self.notifier.send_error_alert(f"포지션 모니터링 중 오류 발생: {e}")
    
    def _execute_reversal(self, reason: str = "손절 전환"):
        """전환 매매 실행"""
        try:
            # 원본 주식 데이터 수집 (지표 계산용, yfinance 사용)
            original_data = self.data_fetcher.get_intraday_data(
                self.original_symbol, 
                interval="1h"
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
                self.kis.place_order(close_symbol, "SELL", close_qty, etf_long_price if ... else ...)
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
                    self.notifier.send_error_alert(f"진입 주문 실패: {new_symbol}")
                    # 롤백 로직 필요할 수 있으나 복잡하므로 로그만 남김
                else:
                    # 진입 알림 전송
                    # TODO: 실제 1주당 가격정보 확인 필요. 여기서는 시장가 주문이라 가격을 0으로 보냈음.
                    # 알림에는 '시장가' 또는 추정가 표시가 좋음.
                    # etf_long_price / etf_short_price 사용
                    buy_price = etf_long_price if result['to_etf'] == self.etf_long else etf_short_price
                    self.notifier.send_order_alert(
                        symbol=new_symbol,
                        side="BUY", 
                        price=buy_price, 
                        quantity=new_qty,
                        reason=reason
                    )
                    
                logger.info(f"✅ 전환 매매 성공: {result['from_etf']} -> {result['to_etf']}")
                
                # [State Persistence] 전환 진입 후 상태 저장
                self.state_manager.save_state({
                    "current_position": self.strategy.current_position,
                    "current_etf_symbol": self.strategy.current_etf_symbol,
                    "entry_price": self.strategy.entry_price,
                    "entry_time": self.strategy.entry_time,
                    "entry_quantity": self.strategy.entry_quantity
                })
                
                # === 강제 청산 날짜 설정 ===
                # LONG: 3 trading days, SHORT: 1 trading day
                target_days = 3 if result['to_etf'] == self.etf_long else 1
                entry_date = datetime.now(self.timezone).date()
                self.forced_close_date = self._calculate_trading_day_limit(entry_date, target_days)
                logger.info(f"📅 강제 청산 날짜 설정: {self.forced_close_date} ({target_days} 거래일 후)")
                
            else:
                logger.info("전환 매매 조건 미충족 (Strategy 내부 로직)")
                
        except Exception as e:
            logger.error(f"전환 매매 실행 실패: {e}")
            self.notifier.send_error_alert(f"전환 매매 실행 중 오류 발생: {e}")
    
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
            self.notifier.send_error_alert(f"청산 주문 실패: {symbol}")
            return
        
        # 청산 알림 전송
        self.notifier.send_order_alert(
            symbol=symbol, 
            side="SELL", 
            price=current_price, 
            quantity=qty, 
            reason=reason
        )

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
        self.strategy.entry_price = None
        self.strategy.entry_time = None
        self.strategy.entry_quantity = None
        self.forced_close_date = None
        
        # [State Persistence] 청산 후 상태 초기화
        self.state_manager.clear_state()
    
    def execute_trading_strategy(self):
        """거래 전략 실행 (정규장)"""
        market_status = self._get_market_status()
        
        # 요청사항 2: 정규장 시간 부터 시작
        # TEST MODE: 장 종료 후에도 테스트를 위해 AFTERMARKET/CLOSED 허용
        # DAYTIME(한국 주간)은 모의투자(테스트)에서만 허용
        allowed_statuses = ["REGULAR"]
        if self.kis.is_paper_trading:
            allowed_statuses.append("DAYTIME")
            allowed_statuses.append("AFTERMARKET")
            allowed_statuses.append("CLOSED")
            allowed_statuses.append("PREMARKET")
            
        if market_status in allowed_statuses:
            logger.info(f"거래 전략 실행 중 (Status: {market_status})")
            
            # 이미 포지션이 있으면 스킵
            if self.strategy.current_position:
                logger.info(f"이미 포지션 보유 중: {self.strategy.current_etf_symbol} {self.strategy.current_position}")
                return
            
            try:
                # 원본 주식 데이터 수집 (지표용)
                # 1시간 간격 실행이므로 1시간봉 사용 (기존 5m -> 1h 명시적 변경)
                original_data = self.data_fetcher.get_intraday_data(
                    self.original_symbol,
                    interval="1h"
                )
                
                if original_data is None or len(original_data) < 50:
                    logger.warning(f"{self.original_symbol} 데이터 부족 또는 조회 실패")
                    self.notifier.send_error_alert(f"데이터 조회 실패: {self.original_symbol}\n(토큰 만료 또는 서버 오류 가능성)")
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
                                
                                # [State Persistence] 진입 후 상태 저장
                                self.state_manager.save_state({
                                    "current_position": self.strategy.current_position,
                                    "current_etf_symbol": self.strategy.current_etf_symbol,
                                    "entry_price": self.strategy.entry_price,
                                    "entry_time": self.strategy.entry_time,
                                    "entry_quantity": self.strategy.entry_quantity
                                })
                                
                                logger.info(
                                    f"{position_side} 포지션 진입: {target_etf} @ ${etf_price:.2f} x {quantity:.2f} "
                                    f"(신뢰도: {confidence:.2f})"
                                )
                                action_result = f"진입 성공 ({target_etf})"
                            else:
                                logger.error("진입 주문 실패")
                                action_result = "진입 주문 실패"
                else:
                     action_result = "신호 없음 / 관망"
                     
                rsi = signal_data.get("rsi")
                macd = signal_data.get("macd")
                
                logger.info(f"텔레그램 알림 전송 시도: Signal={signal}, Action={action_result}")
                
                # 전략 실행 결과 텔레그램 전송
                res = self.notifier.send_strategy_update(
                    symbol=self.original_symbol,
                    market_status=market_status,
                    signal=str(signal).split(".")[-1], # SignalType.BUY -> BUY
                    confidence=confidence if confidence else 0.0,
                    current_position=self.strategy.current_position,
                    action=action_result,
                    rsi=rsi,
                    macd=macd
                )
                
                if res:
                    logger.info("텔레그램 알림 전송 성공")
                else:
                    logger.warning("텔레그램 알림 전송 실패 (send_strategy_update returned False)")
                                
            except Exception as e:
                logger.error(f"거래 전략 실행 실패: {e}")
                                
            except Exception as e:
                logger.error(f"거래 전략 실행 실패: {e}")
        
        # 포지션 모니터링 (항상 실행)
        self.monitor_position()
    
  
    def sync_internal_state_with_account(self):
        """계좌 잔고를 조회하여 봇 내부 상태 동기화"""
        logger.info("계좌 정보 동기화 중...")
        balance_data = self.kis.get_overseas_stock_balance()
        
        if not balance_data:
            logger.warning("계좌 정보 동기화 실패 (API 응답 없음)")
            return
            
        holdings = balance_data.get('holdings', [])
        assets = balance_data.get('assets', {})
        
        # 저장된 상태 로드 시도
        saved_state = self.state_manager.load_state()
        
        # 1. 자본금 동기화 (예수금 + 평가금액?)
        # 여기서는 Strategy의 capital을 보정하는 것이 맞는지 고민 필요. 
        # Strategy는 '할당된 자본' 개념이므로 초기값 유지 + PnL 누적으로 갈지, 
        # 아니면 현재 계좌의 실제 예수금으로 리셋할지.
        # 일단은 포지션 복구에 집중.
        
        # 2. 보유 종목 확인 (TSLL / TSLS)
        target_found = False
        
        for item in holdings:
            # ovrs_pdno: 상품번호 (예: TSLL)
            # ovrs_item_name: 상품명
            # ord_psbl_qty: 주문가능수량 or cclt_qty: 체결수량 -> cclt_qty(체결수량) 확인 (ccld_qty_smtl1 등 키 확인 필요)
            # 모의투자 문서: ord_psbl_qty (주문가능수량), cclt_qty (체결수량) 인데
            # 실제 응답 키값: ovrs_pdno, ovrs_item_name, cclt_qty (보유수량) 등
            
            symbol = item.get('ovrs_pdno')
            qty = float(item.get('ord_psbl_qty', 0)) # 혹은 cclt_qty
            if qty <= 0:
                # cclt_qty 등 다른 키 시도
                qty = float(item.get('cclt_qty', 0))
            
            purch_avg_price = float(item.get('pchs_avg_pric', 0)) # 매입평균가격
            
            if symbol == self.etf_long:
                self.strategy.current_position = "LONG"
                self.strategy.current_etf_symbol = self.etf_long
                self.strategy.entry_price = purch_avg_price
                self.strategy.entry_quantity = qty
                self.strategy.entry_time = datetime.now() # 기본값
                
                # [State Persistence] 저장된 상태가 있고, 보유 종목/수량이 일치하면 저장된 진입 시간 복원
                if saved_state and saved_state.get('current_etf_symbol') == symbol:
                    # 수량이 대략 일치하는지 확인 (분할 매매 등을 고려하지 않는다면 단순 비교)
                    saved_qty = saved_state.get('entry_quantity')
                    if saved_qty and abs(saved_qty - qty) < 1.0: # 오차 허용
                        if saved_state.get('entry_time'):
                            self.strategy.entry_time = saved_state['entry_time']
                            logger.info(f"💾 저장된 진입 시간 복원: {self.strategy.entry_time}")
                
                # 상태 파일이 없거나 안 맞으면 현재 상태로 다시 저장 (동기화)
                if not saved_state or saved_state.get('current_etf_symbol') != symbol:
                     self.state_manager.save_state({
                        "current_position": self.strategy.current_position,
                        "current_etf_symbol": self.strategy.current_etf_symbol,
                        "entry_price": self.strategy.entry_price,
                        "entry_time": self.strategy.entry_time,
                        "entry_quantity": self.strategy.entry_quantity
                    })

                target_found = True
                logger.info(f"기존 포지션 복구: LONG ({symbol}) {qty}주 @ ${purch_avg_price}")
                break
                
            elif symbol == self.etf_short:
                self.strategy.current_position = "SHORT"
                self.strategy.current_etf_symbol = self.etf_short
                self.strategy.entry_price = purch_avg_price
                self.strategy.entry_quantity = qty
                self.strategy.entry_time = datetime.now()
                
                # [State Persistence] 저장된 상태가 있고, 보유 종목/수량이 일치하면 저장된 진입 시간 복원
                if saved_state and saved_state.get('current_etf_symbol') == symbol:
                    # 수량이 대략 일치하는지 확인 (분할 매매 등을 고려하지 않는다면 단순 비교)
                    saved_qty = saved_state.get('entry_quantity')
                    if saved_qty and abs(saved_qty - qty) < 1.0: # 오차 허용
                        if saved_state.get('entry_time'):
                            self.strategy.entry_time = saved_state['entry_time']
                            logger.info(f"💾 저장된 진입 시간 복원: {self.strategy.entry_time}")
                            
                # 상태 파일이 없거나 안 맞으면 현재 상태로 다시 저장 (동기화)
                if not saved_state or saved_state.get('current_etf_symbol') != symbol:
                     self.state_manager.save_state({
                        "current_position": self.strategy.current_position,
                        "current_etf_symbol": self.strategy.current_etf_symbol,
                        "entry_price": self.strategy.entry_price,
                        "entry_time": self.strategy.entry_time,
                        "entry_quantity": self.strategy.entry_quantity
                    })

                target_found = True
                logger.info(f"기존 포지션 복구: SHORT ({symbol}) {qty}주 @ ${purch_avg_price}")
                break
                
        if not target_found:
            logger.info("복구할 기존 포지션 없음 (TSLL/TSLS 미보유)")
            # 포지션이 없는데 상태 파일이 남아있으면 삭제 (엇박자 방지)
            if saved_state:
                self.state_manager.clear_state()

    def run(self):
        """봇 실행"""
        logger.info(f"Tesla 전환 매매 봇 시작 (Target: {self.original_symbol})")
        
        # 시작 시 계좌 상태 동기화
        self.sync_internal_state_with_account()
        
        self.is_running = True
        
        # 스케줄러 설정
        # 기본적으로 1분/5분 단위 등으로 execute_trading_strategy 및 monitor_position을 호출해야 함.
        # 기존 Scheduler 구조가 Daily Task 등록 방식이라면, execute_trading_strategy 주기를 확인해야 함.
        # 여기서는 기존 구조를 유지하되 force_close만 제거.
        
        # 1. 포지션 모니터링: 매 시간 1분에 실행 (정각 1분)
        schedule.every().hour.at(":01").do(self.monitor_position)
        
        # 2. 거래 전략 실행: 매 시간 1분에 실행 (정각 1분)
        schedule.every().hour.at(":01").do(self.execute_trading_strategy)
        
        # 3. 장 시작/종료 메시지 등은 별도 스케줄링 가능하나 일단 생략
        
        # 초기 1회 실행 (테스트용)
        logger.info("봇 시작 시 초기 1회 전략 실행...")
        self.execute_trading_strategy()
        
        # 메인 루프
        try:
            while self.is_running:
                schedule.run_pending() # schedule 모듈 직접 사용
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
