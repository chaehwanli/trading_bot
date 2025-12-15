"""
전환 매매 전략 백테스트
Reverse/Flip Trading Strategy 백테스트 실행
"""
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, get_etf_by_original, REVERSAL_STRATEGY_PARAMS
from data.data_fetcher import DataFetcher
from backtester.engine import prepare_dataset
from strategy.reversal_strategy import ReversalStrategy
from strategy.signal_generator import SignalType
from utils.logger import logger
import pytz
import pandas_market_calendars as mcal

import warnings
warnings.filterwarnings(
    "ignore",
    message=".*break_start.*break_end.*"
)

class ReversalBacktester:
    """전환 매매 전략 백테스트 클래스"""
    
    def __init__(self, params: dict = None, source: str = "kis"):
        # self.data_fetcher = DataFetcher() # Deprecated
        self.strategy = ReversalStrategy(params=params)
        self.source = source
        self.trades = []
        self.equity_curve = []
        self.fee_rate = 0.0025  # 거래 수수료율 (예: 0.25%)
        # Timezone 설정
        self.timezone = pytz.timezone("Asia/Seoul")
        
        # 거래일 캘린더 (백테스트 시작 시 1회 생성)
        self.trading_days = None          # list[date]
        self.trading_day_index = None     # dict[date, int]

        # 강제청산 날짜
        self.forced_close_date = None
        # STOP_LOSS 쿨다운 종료일
        self.cooldown_until_date = None

    def build_trading_calendar(self, start_dt, end_dt, market: str):
        """
        거래일 캘린더를 1회 생성
        """
        if market == "US":
            cal = mcal.get_calendar("NYSE")
        elif market == "KR":
            cal = mcal.get_calendar("XKRX")
        else:
            raise ValueError(f"Unsupported market: {market}")

        schedule = cal.schedule(
            start_date=start_dt.date(),
            end_date=end_dt.date()
        )

        self.trading_days = list(schedule.index.date)
        self.trading_day_index = {
            d: i for i, d in enumerate(self.trading_days)
        }

    def _is_dst(self, dt: datetime) -> bool:
        """
        주어진 날짜(dt)가 미국 DST(서머타임) 적용 기간인지 확인.
        dt는 timezone-aware(Asia/Seoul 등) 또는 native datetime일 수 있음.
        기준은 US/Eastern 시간으로 변환하여 확인.
        """
        eastern = pytz.timezone('US/Eastern')
        
        # dt가 timezone 정보가 없다면, 한국 시간으로 가정하고 localize
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
            
        # US/Eastern으로 변환
        dt_eastern = dt.astimezone(eastern)
        return bool(dt_eastern.dst())

    def _get_market_status(self, dt: datetime) -> str:
        """
        주어진 시간(dt)의 시장 상태 반환.
        dt는 timezone-aware여야 하며, 이를 Korea Standard Time(KST)으로 변환하여
        00:00~24:00 기준 분(minute)을 계산해 상태를 판별한다.
        """
        if dt.tzinfo is None:
            # naive라면 KST localizing (가정)
            dt = self.timezone.localize(dt)
        
        # KST로 변환
        dt_kr = dt.astimezone(self.timezone)
        
        current_time = dt_kr.time()
        curr_min = current_time.hour * 60 + current_time.minute
        
        is_dst = self._is_dst(dt)
        
        if is_dst: # Summer Time (US DST Active)
            # Daytime: 10:00 ~ 17:00
            if 600 <= curr_min < 1020: return "DAYTIME"
            # Premarket: 17:00 ~ 22:30
            if 1020 <= curr_min < 1350: return "PREMARKET"
            # Regular: 22:30 ~ 05:00 (Next day)
            # 22:30 = 1350, 24:00 = 1440. 05:00 = 300.
            if 1350 <= curr_min or curr_min < 300: return "REGULAR"
            # Aftermarket: 05:00 ~ 07:00
            if 300 <= curr_min < 420: return "AFTERMARKET"
            # Extended: 07:00 ~ 09:00
            if 420 <= curr_min < 540: return "EXTENDED"
        else: # Winter Time (US DST Inactive)
            # Daytime: 10:00 ~ 18:00
            if 600 <= curr_min < 1080: return "DAYTIME"
            # Premarket: 18:00 ~ 23:30
            if 1080 <= curr_min < 1410: return "PREMARKET"
            # Regular: 23:30 ~ 06:00 (Next day)
            # 23:30 = 1410. 06:00 = 360.
            if 1410 <= curr_min or curr_min < 360: return "REGULAR"
            # Aftermarket: 06:00 ~ 07:00
            if 360 <= curr_min < 420: return "AFTERMARKET"
            # Extended: 07:00 ~ 09:00
            if 420 <= curr_min < 540: return "EXTENDED"
            
        return "CLOSED"
    
    def run_backtest(
        self,
        original_symbol: str,
        etf_long: str,
        etf_long_multiple: str,
        etf_short: str,
        etf_short_multiple: str,
        start_date: str,
        end_date: str,
        interval: str = "1h"
    ):
        """
        백테스트 실행
        
        Args:
            original_symbol: 원본 주식 심볼
            etf_long: 롱 ETF 심볼
            etf_short: 숏 ETF 심볼
            start_date: 시작 날짜
            end_date: 종료 날짜
            interval: 데이터 간격
        """
        print(f"\n{'='*70}")
        print(f"전환 매매 전략 백테스트 시작")
        print(f"원본 주식: {original_symbol} -> {etf_long} {etf_long_multiple} /{etf_short} {etf_short_multiple}")
        print(f"기간: {start_date} ~ {end_date}")
        print(f"초기 자본: ${self.strategy.initial_capital:.2f}")
        print(f"{'='*70}\n")
        
        # 데이터 수집 (로컬 CSV 로드)
        print(f"데이터 로딩 중 (Local CSV from {self.source})...")
        try:
            # prepare_dataset loads data and applies indicators if needed
            original_data = prepare_dataset(original_symbol, interval, source=self.source)
            etf_long_data = prepare_dataset(etf_long, interval, source=self.source)
            etf_short_data = prepare_dataset(etf_short, interval, source=self.source)

        except Exception as e:
            print(f"❌ 데이터 로딩 실패: {e}")
            return None
        
        # 날짜 필터링
        original_data.index = pd.to_datetime(original_data.index)
        etf_long_data.index = pd.to_datetime(etf_long_data.index)
        etf_short_data.index = pd.to_datetime(etf_short_data.index)
        
        mask_original = (original_data.index >= start_date) & (original_data.index <= end_date)
        mask_long = (etf_long_data.index >= start_date) & (etf_long_data.index <= end_date)
        mask_short = (etf_short_data.index >= start_date) & (etf_short_data.index <= end_date)
        
        original_data = original_data.loc[mask_original].copy()
        etf_long_data = etf_long_data.loc[mask_long].copy()
        etf_short_data = etf_short_data.loc[mask_short].copy()
        
        if original_data.empty or etf_long_data.empty or etf_short_data.empty:
            print("❌ 지정된 기간에 데이터가 없습니다")
            return None
        
        print(f"✅ 데이터 수집 완료: 원본 {len(original_data)}개, 롱 {len(etf_long_data)}개, 숏 {len(etf_short_data)}개\n")
        
        # 공통 인덱스
        common_index = original_data.index.intersection(etf_long_data.index).intersection(etf_short_data.index)
        common_index = common_index.sort_values()
        
        # 거래일 캘린더 생성 (1회)
        self.build_trading_calendar(
            start_dt=common_index[0],
            end_dt=common_index[-1],
            market="US"   # ETF 기준 (현재 코드 기준)
        )
        
        # 백테스트 실행
        for i in range(50, len(common_index)):
            current_time = common_index[i]
            
            # 원본 주식 데이터 (신호 생성용)
            original_mask = original_data.index <= current_time
            original_current_data = original_data.loc[original_mask]

            # LONG/SHORT ETF 데이터
            etf_long_mask = etf_long_data.index <= current_time
            etf_short_mask = etf_short_data.index <= current_time
            etf_long_current_data = etf_long_data.loc[etf_long_mask]
            etf_short_current_data = etf_short_data.loc[etf_short_mask]
            
            if len(original_current_data) < 50:
                continue
            
            # ETF 가격 조회
            try:
                etf_long_price = etf_long_data.loc[etf_long_data.index <= current_time, 'close'].iloc[-1]
                etf_short_price = etf_short_data.loc[etf_short_data.index <= current_time, 'close'].iloc[-1]
            except (IndexError, KeyError):
                continue
            
            # 신호 생성
            #print(f"📈 신호 생성 시도 [{current_time.strftime('%Y-%m-%d %H:%M')}] ")
            signal_data = self.strategy.signal_generator.generate_signal(
                original_current_data,
                self.strategy.current_position
            )
            
            # 시장 시간 체크
            market_status = self._get_market_status(current_time)
            #is_tradable = market_status in ["PREMARKET", "REGULAR"] # 주간거래는 제외(데이터가 보통 미국장 기준일 것임. KIS API 로직 따름)
            is_tradable = market_status in ["REGULAR"] # 주간거래는 제외(데이터가 보통 미국장 기준일 것임. KIS API 로직 따름)
            
            # 디버깅용 출력 (초반)
            if i < 60:
                 print(f"DEBUG: {current_time} Status={market_status} Tradable={is_tradable} DST={self._is_dst(current_time)}")
            
            signal = signal_data['signal']
            confidence = signal_data['confidence']
            
            # 포지션이 없는 경우 진입 (거래 가능 시간에만)
            #if not self.strategy.current_position and is_tradable:
            if (
                not self.strategy.current_position
                and is_tradable
                and (
                    self.cooldown_until_date is None
                    or current_time.date() >= self.cooldown_until_date
                )
            ):
                if signal == SignalType.BUY and confidence > 0.5:
                    quantity = self.strategy.calculate_position_size(etf_long_price, is_reversal=False)
                    if quantity > 0:
                        trade_amount = etf_long_price * quantity
                        fee = trade_amount * self.fee_rate
                        self.strategy.capital -= (trade_amount + fee)
                        
                        self.strategy.current_position = "LONG"
                        self.strategy.current_etf_symbol = etf_long
                        self.strategy.entry_price = etf_long_price
                        self.strategy.entry_time = current_time
                        self.strategy.entry_quantity = quantity
                        
                        print(f"📈 [{current_time.strftime('%Y-%m-%d %H:%M')}] {original_symbol} -> {etf_long} 롱 진입 @ ${etf_long_price:.2f} x {quantity:.2f} (수수료: ${fee:.2f})")

                        # === 강제청산 날짜 계산 (LONG) ===
                        entry_date = current_time.date()
                        idx = self.trading_day_index.get(entry_date)

                        if idx is not None:
                            max_hold_days_long = 3
                            close_idx = idx + max_hold_days_long
                            if close_idx < len(self.trading_days):
                                self.forced_close_date = self.trading_days[close_idx]
                            else:
                                self.forced_close_date = self.trading_days[-1]
                
                elif signal == SignalType.SELL and confidence > 0.5:
                    quantity = self.strategy.calculate_position_size(etf_short_price, is_reversal=False)
                    if quantity > 0:
                        trade_amount = etf_short_price * quantity
                        fee = trade_amount * self.fee_rate
                        self.strategy.capital -= (trade_amount + fee)
                        
                        self.strategy.current_position = "SHORT"
                        self.strategy.current_etf_symbol = etf_short
                        self.strategy.entry_price = etf_short_price
                        self.strategy.entry_time = current_time
                        self.strategy.entry_quantity = quantity
                        
                        print(f"📉 [{current_time.strftime('%Y-%m-%d %H:%M')}] {original_symbol} -> {etf_short} 숏 진입 @ ${etf_short_price:.2f} x {quantity:.2f} (수수료: ${fee:.2f})")

                        # === 강제청산 날짜 계산 (SHORT) ===
                        entry_date = current_time.date()
                        idx = self.trading_day_index.get(entry_date)

                        if idx is not None:
                            max_hold_days_short = 1
                            close_idx = idx + max_hold_days_short
                            if close_idx < len(self.trading_days):
                                self.forced_close_date = self.trading_days[close_idx]
                            else:
                                self.forced_close_date = self.trading_days[-1]
            
            # 포지션 모니터링
            if self.strategy.current_position:
                current_etf_price = etf_long_price if self.strategy.current_position == "LONG" else etf_short_price
                current_etf_multiple = etf_long_multiple if self.strategy.current_position == "LONG" else etf_short_multiple
                # 손절/익절 확인
                exit_reason = self.strategy.check_stop_loss_take_profit2(current_etf_price, current_etf_multiple)
                
                if exit_reason:
                    # 손절/익절인 경우 무조건 청산 (전환 안함)
                    #if exit_reason == "STOP_LOSS":
                    #    self._close_position(current_time, current_etf_price, exit_reason)
                    if exit_reason == "STOP_LOSS":
                        self._close_position(current_time, current_etf_price, exit_reason)

                        # === STOP_LOSS 쿨다운 설정 (4 거래일) ===
                        stop_date = current_time.date()
                        idx = self.trading_day_index.get(stop_date)

                        if idx is not None:
                            cooldown_days = 4
                            cooldown_idx = idx + cooldown_days
                            if cooldown_idx < len(self.trading_days):
                                self.cooldown_until_date = self.trading_days[cooldown_idx]
                            else:
                                self.cooldown_until_date = self.trading_days[-1]

                        print(f"⛔ STOP_LOSS 쿨다운 시작 → {self.cooldown_until_date}")
                    elif exit_reason == "TAKE_PROFIT":
                        # 익절인 경우 청산
                        self._close_position(current_time, current_etf_price, exit_reason)
                    else:
                        # 기타 사유 청산
                        print(f"기타 사유 청산 → {exit_reason}")
                        self._close_position(current_time, current_etf_price, exit_reason)

                # === 거래일 기준 강제청산 ===
                if self.strategy.current_position and self.forced_close_date:
                    # 손익 판단 (강제청산 직전 기준)
                    is_loss = current_etf_price < self.strategy.entry_price
                    if current_time.date() >= self.forced_close_date:
                        self._close_position(
                            current_time,
                            current_etf_price,
                            "FORCE_CLOSE_TRADING_DAY_LIMIT"
                        )
                        # === FORCE_CLOSE 손실 시 쿨다운 1 거래일 ===
                        if is_loss:
                            force_close_date = current_time.date()
                            idx = self.trading_day_index.get(force_close_date)

                            if idx is not None:
                                cooldown_days = 1
                                cooldown_idx = idx + cooldown_days
                                if cooldown_idx < len(self.trading_days):
                                    self.cooldown_until_date = self.trading_days[cooldown_idx]
                                else:
                                    self.cooldown_until_date = self.trading_days[-1]

                            print(f"⚠️ FORCE_CLOSE 손실 → 쿨다운 1일 적용 ({self.cooldown_until_date})")

            # 자본 추적
            if self.strategy.current_position and self.strategy.entry_price:
                if self.strategy.current_position == "LONG":
                    current_etf_price = etf_long_price
                else:
                    current_etf_price = etf_short_price

                pnl_pct = ((current_etf_price - self.strategy.entry_price) / self.strategy.entry_price) * 100
                
                pnl = self.strategy.entry_quantity * self.strategy.entry_price * (pnl_pct / 100)
                estimated_capital = self.strategy.capital + self.strategy.entry_quantity * self.strategy.entry_price + pnl
            else:
                estimated_capital = self.strategy.capital
            
            self.equity_curve.append({
                'time': current_time,
                'capital': estimated_capital
            })
        
        # 마지막 포지션 청산
        if self.strategy.current_position:
            final_time = common_index[-1]
            try:
                if self.strategy.current_position == "LONG":
                    final_price = etf_long_data.loc[etf_long_data.index <= final_time, 'close'].iloc[-1]
                else:
                    final_price = etf_short_data.loc[etf_short_data.index <= final_time, 'close'].iloc[-1]
                
                self._close_position(final_time, final_price, "FINAL_CLOSE")
            except (IndexError, KeyError):
                pass
        
        # 결과 출력
        self._print_results()
        
        return {
            'trades': self.strategy.trade_history,
            'reversals': self.strategy.reversal_history,
            'equity_curve': self.equity_curve,
            'final_capital': self.strategy.capital,
            'total_pnl': self.strategy.capital - self.strategy.initial_capital,
            'total_fee': sum(t.get('fee', 0) for t in self.strategy.trade_history)
        }

    def _close_position(self, exit_time, exit_price: float, reason: str):
        """포지션 청산"""
        if not self.strategy.current_position or not self.strategy.entry_price:
            return
        
        trade_amount = self.strategy.entry_quantity * exit_price
        fee = trade_amount * self.fee_rate
        
        pnl_pct = ((exit_price - self.strategy.entry_price) / self.strategy.entry_price) * 100
        
        pnl = self.strategy.entry_quantity * self.strategy.entry_price * (pnl_pct / 100)
        self.strategy.capital += self.strategy.entry_quantity * self.strategy.entry_price + pnl - fee
        
        trade_record = {
            'entry_time': self.strategy.entry_time,
            'exit_time': exit_time,
            'symbol': self.strategy.current_etf_symbol,
            'side': self.strategy.current_position,
            'entry_price': self.strategy.entry_price,
            'exit_price': exit_price,
            'quantity': self.strategy.entry_quantity,
            'pnl': pnl - fee,
            'pnl_pct': pnl_pct,
            'fee': fee,
            'reason': reason
        }
        self.strategy.trade_history.append(trade_record)
        
        print(f"🔒 [{exit_time.strftime('%Y-%m-%d %H:%M')}] {self.strategy.current_etf_symbol} {self.strategy.current_position} 청산 @ ${self.strategy.entry_price:.2f} ${exit_price:.2f} (손익: {pnl_pct:.2f}%, 수수료: ${fee:.2f}) - {reason}")
        
        # 포지션 초기화
        self.strategy.current_position = None
        self.strategy.current_etf_symbol = None
        self.strategy.entry_price = None
        self.strategy.entry_time = None
        self.strategy.entry_quantity = None

        # 강제청산 날짜 초기화
        self.forced_close_date = None
    
    def _print_results(self):
        """백테스트 결과 출력"""
        if not self.strategy.trade_history:
            print("\n❌ 거래가 없습니다.")
            return
        
        print(f"\n{'='*70}")
        print("📊 전환 매매 전략 백테스트 결과")
        print(f"{'='*70}\n")
        
        total_trades = len(self.strategy.trade_history)
        total_reversals = len(self.strategy.reversal_history)
        winning_trades = [t for t in self.strategy.trade_history if t['pnl'] > 0]
        losing_trades = [t for t in self.strategy.trade_history if t['pnl'] < 0]
        
        total_pnl = sum(t['pnl'] for t in self.strategy.trade_history)
        total_pnl_pct = (total_pnl / self.strategy.initial_capital) * 100
        
        win_rate = (len(winning_trades) / total_trades * 100)
        
        print(f"💰 자본 변화")
        print(f"  초기 자본:     ${self.strategy.initial_capital:>12,.2f}")
        print(f"  최종 자본:     ${self.strategy.capital:>12,.2f}")
        pnl_sign = "+" if total_pnl >= 0 else ""
        print(f"  총 손익:       {pnl_sign}${total_pnl:>11,.2f} ({pnl_sign}{total_pnl_pct:>6.2f}%)")
        
        print(f"\n📈 거래 통계")
        print(f"  총 거래 횟수:  {total_trades:>12}회")
        print(f"  전환 매매 횟수: {total_reversals:>12}회")
        print(f"  승리 거래:     {len(winning_trades):>12}회 ({win_rate:>6.2f}%)")
        print(f"  손실 거래:     {len(losing_trades):>12}회 ({100-win_rate:>6.2f}%)")
        
        if winning_trades:
            avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
            print(f"  평균 수익:     ${avg_win:>12,.2f}")
        
        if losing_trades:
            avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
            print(f"  평균 손실:     ${avg_loss:>12,.2f}")
        
        print(f"\n{'='*70}\n")

        # 거래 내역 상세 출력 (수수료 포함)
        print("📋 거래 내역:")
        print("-" * 70)
        for i, trade in enumerate(self.strategy.trade_history, 1):
            print(f"{i}. {trade['entry_time'].strftime('%Y-%m-%d %H:%M')} ~ {trade['exit_time'].strftime('%Y-%m-%d %H:%M')}")
            print(f"   {trade['symbol']} {trade['side']} | 진입가: ${trade['entry_price']:.2f} | 청산가: ${trade['exit_price']:.2f} | 수량: {trade['quantity']:.2f}")
            print(f"   손익: ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%) | 수수료: ${trade['fee']:.2f} | 사유: {trade['reason']}")

        # 전환 매매 내역
        if self.strategy.reversal_history:
            print("🔄 전환 매매 내역:")
            print("-" * 70)
            for i, rev in enumerate(self.strategy.reversal_history, 1):
                print(f"{i}. {rev['from_etf']} ({rev['from_position']}) -> {rev['to_etf']} ({rev['to_position']})")
                print(f"   시간: {rev['time'].strftime('%Y-%m-%d %H:%M')} | 가격: ${rev['entry_price']:.2f} | 이유: {rev['reason']}")
        
        print(f"\n{'='*70}\n")

def main():
    """백테스트 메인 함수"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, choices=["kis", "yfinance"], default="kis", help="Data source")
    parser.add_argument("--start-date", type=str, default=None, help="Backtest start date (YYYY-MM-DD). Default: 1 year ago")
    parser.add_argument("--end-date", type=str, default=None, help="Backtest end date (YYYY-MM-DD). Default: today")
    parser.add_argument("--use-all-data", action="store_true", help="Use all available data from files (ignores start/end date)")
    args = parser.parse_args()

    # 결과 파일 초기화 (source에 따라 다른 파일명 사용)
    result_file = f"{args.source}_result.txt"
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(f"전환 매매 전략 백테스트 결과 [Source: {args.source}] ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
        f.write("="*70 + "\n\n")
    
    interval = "1h"
    
    # 백테스트 기간 설정
    if args.use_all_data:
        # 데이터 파일에서 실제 날짜 범위를 읽어옴
        # 첫 번째 심볼의 데이터로 날짜 범위 확인
        first_symbol = TARGET_SYMBOLS[0]["ORIGINAL"]
        try:
            sample_data = prepare_dataset(first_symbol, interval, source=args.source)
            start_date = sample_data.index.min().strftime("%Y-%m-%d")
            end_date = sample_data.index.max().strftime("%Y-%m-%d")
            logger.info(f"Using all available data: {start_date} to {end_date}")
        except Exception as e:
            logger.warning(f"Could not read date range from data files: {e}. Using default 1 year.")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
    else:
        # 수동 지정 또는 기본값
        if args.end_date:
            end_date = args.end_date
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        if args.start_date:
            start_date = args.start_date
        else:
            # 기본값: 1년 전
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    
    total_symbols = len(TARGET_SYMBOLS)

    for i, target_item in enumerate(TARGET_SYMBOLS):
        original_symbol = target_item["ORIGINAL"]
        etf_long = target_item["LONG"]
        etf_long_multiple = target_item["LONG_MULTIPLE"]
        etf_short = target_item["SHORT"]
        etf_short_multiple = target_item["SHORT_MULTIPLE"]
        
        # 전략 파라미터 설정
        params = REVERSAL_STRATEGY_PARAMS.copy()
        params["symbol"] = original_symbol
        params["capital"] = 1200
        params["reverse_trigger"] = False
        params["reverse_mode"] = "full"
        
        backtester = ReversalBacktester(params=params, source=args.source)
        
        print(f"\n{'='*20} [{i+1}/{total_symbols}] {original_symbol} 백테스트 시작 {'='*20}")
        print(f"LONG: {etf_long} ({etf_long_multiple}) / SHORT: {etf_short} ({etf_short_multiple})")
        
        results = backtester.run_backtest(
            original_symbol=original_symbol,
            etf_long=etf_long,
            etf_long_multiple=etf_long_multiple,
            etf_short=etf_short,
            etf_short_multiple=etf_short_multiple,
            start_date=start_date,
            end_date=end_date,
            interval=interval
        )
        
        # 결과 파일에 누적
        with open(result_file, "a", encoding="utf-8") as f:
            f.write(f"[{i+1}/{total_symbols}] {original_symbol} 결과\n")
            f.write(f"LONG: {etf_long} ({etf_long_multiple}) / SHORT: {etf_short} ({etf_short_multiple})\n")
            
            if results:
                trades = results['trades']
                # 전체 통계
                win_rate = 0
                winning_trades = [t for t in trades if t['pnl'] > 0]
                if trades:
                    win_rate = (len(winning_trades) / len(trades) * 100)
                
                f.write(f"총 거래: {len(trades)}회\n")
                f.write(f"전환 매매: {len(results['reversals'])}회\n")
                f.write(f"승률: {win_rate:.2f}% ({len(winning_trades)}/{len(trades)})\n")
                f.write(f"최종 자본: ${results['final_capital']:,.2f}\n")
                f.write(f"총 손익: ${results['total_pnl']:,.2f}\n")
                f.write(f"총 수수료: ${results['total_fee']:,.2f}\n")
                
                # LONG/SHORT 상세 통계
                long_trades = [t for t in trades if t['side'] == 'LONG']
                short_trades = [t for t in trades if t['side'] == 'SHORT']
                
                def calculate_stats(trade_list):
                    if not trade_list:
                        return "거래 없음", 0, 0, 0, None, None
                    
                    wins = [t for t in trade_list if t['pnl'] > 0]
                    win_rate = (len(wins) / len(trade_list) * 100)
                    
                    max_profit_trade = max(trade_list, key=lambda x: x['pnl'])
                    max_loss_trade = min(trade_list, key=lambda x: x['pnl'])
                    
                    max_profit = max_profit_trade['pnl']
                    max_loss = max_loss_trade['pnl']
                    
                    return f"{win_rate:.2f}% ({len(wins)}/{len(trade_list)})", len(trade_list), max_profit, max_loss, max_profit_trade, max_loss_trade

                long_win_rate, long_count, long_max_profit, long_max_loss, long_max_trade, long_min_trade = calculate_stats(long_trades)
                short_win_rate, short_count, short_max_profit, short_max_loss, short_max_trade, short_min_trade = calculate_stats(short_trades)
                
                f.write(f"\n[LONG ETF: {etf_long}]\n")
                f.write(f"  거래 횟수: {long_count}회\n")
                f.write(f"  승률: {long_win_rate}\n")
                f.write(f"  최대 수익: ${long_max_profit:.2f}")
                if long_max_trade:
                    f.write(f" (진입: ${long_max_trade['entry_price']:.2f}, 청산: ${long_max_trade['exit_price']:.2f}, 수량: {long_max_trade['quantity']:.2f})")
                f.write("\n")
                f.write(f"  최대 손실: ${long_max_loss:.2f}")
                if long_min_trade:
                    f.write(f" (진입: ${long_min_trade['entry_price']:.2f}, 청산: ${long_min_trade['exit_price']:.2f}, 수량: {long_min_trade['quantity']:.2f})")
                f.write("\n")
                
                f.write(f"\n[SHORT ETF: {etf_short}]\n")
                f.write(f"  거래 횟수: {short_count}회\n")
                f.write(f"  승률: {short_win_rate}\n")
                f.write(f"  최대 수익: ${short_max_profit:.2f}")
                if short_max_trade:
                    f.write(f" (진입: ${short_max_trade['entry_price']:.2f}, 청산: ${short_max_trade['exit_price']:.2f}, 수량: {short_max_trade['quantity']:.2f})")
                f.write("\n")
                f.write(f"  최대 손실: ${short_max_loss:.2f}")
                if short_min_trade:
                    f.write(f" (진입: ${short_min_trade['entry_price']:.2f}, 청산: ${short_min_trade['exit_price']:.2f}, 수량: {short_min_trade['quantity']:.2f})")
                f.write("\n")

            else:
                f.write("거래 없음 또는 데이터 부족\n")
            
            f.write("-" * 50 + "\n\n")
        
        if results:
            print(f"✅ {original_symbol} 완료: 총 손익 ${results['total_pnl']:,.2f}")
            
    print(f"\n🎉 모든 백테스트 완료! 결과가 {result_file}에 저장되었습니다.")

if __name__ == "__main__":
    main()