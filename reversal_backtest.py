"""
전환 매매 전략 백테스트
Reverse/Flip Trading Strategy 백테스트 실행
"""
import sys
import os
from datetime import datetime, timedelta
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, get_etf_by_original, REVERSAL_STRATEGY_PARAMS
from data.data_fetcher import DataFetcher
from strategy.reversal_strategy import ReversalStrategy
from strategy.signal_generator import SignalType
from utils.logger import logger

class ReversalBacktester:
    """전환 매매 전략 백테스트 클래스"""
    
    def __init__(self, params: dict = None):
        self.data_fetcher = DataFetcher()
        self.strategy = ReversalStrategy(params=params)
        self.trades = []
        self.equity_curve = []
    
    def run_backtest(
        self,
        original_symbol: str,
        etf_long: str,
        etf_short: str,
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
        print(f"원본 주식: {original_symbol} -> {etf_long}/{etf_short}")
        print(f"기간: {start_date} ~ {end_date}")
        print(f"초기 자본: ${self.strategy.initial_capital:.2f}")
        print(f"{'='*70}\n")
        
        # 데이터 수집
        print("데이터 수집 중...")
        original_data = self.data_fetcher.get_historical_data(
            original_symbol, period="max", interval=interval
        )
        etf_long_data = self.data_fetcher.get_historical_data(
            etf_long, period="max", interval=interval
        )
        etf_short_data = self.data_fetcher.get_historical_data(
            etf_short, period="max", interval=interval
        )
        
        if original_data is None or etf_long_data is None or etf_short_data is None:
            print("❌ 데이터 수집 실패")
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
        
        # 백테스트 실행
        for i in range(50, len(common_index)):
            current_time = common_index[i]
            
            # 원본 주식 데이터 (신호 생성용)
            original_mask = original_data.index <= current_time
            original_current_data = original_data.loc[original_mask]
            
            if len(original_current_data) < 50:
                continue
            
            # ETF 가격 조회
            try:
                etf_long_price = etf_long_data.loc[etf_long_data.index <= current_time, 'close'].iloc[-1]
                etf_short_price = etf_short_data.loc[etf_short_data.index <= current_time, 'close'].iloc[-1]
            except (IndexError, KeyError):
                continue
            
            # 신호 생성
            signal_data = self.strategy.signal_generator.generate_signal(
                original_current_data,
                self.strategy.current_position
            )
            
            signal = signal_data['signal']
            confidence = signal_data['confidence']
            
            # 포지션이 없는 경우 진입
            if not self.strategy.current_position:
                if signal == SignalType.BUY and confidence > 0.5:
                    quantity = self.strategy.calculate_position_size(etf_long_price, is_reversal=False)
                    if quantity > 0:
                        trade_amount = etf_long_price * quantity
                        self.strategy.capital -= trade_amount
                        
                        self.strategy.current_position = "LONG"
                        self.strategy.current_etf_symbol = etf_long
                        self.strategy.entry_price = etf_long_price
                        self.strategy.entry_time = current_time
                        self.strategy.entry_quantity = quantity
                        
                        print(f"📈 [{current_time.strftime('%Y-%m-%d %H:%M')}] {original_symbol} -> {etf_long} 롱 진입 @ ${etf_long_price:.2f} x {quantity:.2f}")
                
                elif signal == SignalType.SELL and confidence > 0.5:
                    quantity = self.strategy.calculate_position_size(etf_short_price, is_reversal=False)
                    if quantity > 0:
                        trade_amount = etf_short_price * quantity
                        self.strategy.capital -= trade_amount
                        
                        self.strategy.current_position = "SHORT"
                        self.strategy.current_etf_symbol = etf_short
                        self.strategy.entry_price = etf_short_price
                        self.strategy.entry_time = current_time
                        self.strategy.entry_quantity = quantity
                        
                        print(f"📉 [{current_time.strftime('%Y-%m-%d %H:%M')}] {original_symbol} -> {etf_short} 숏 진입 @ ${etf_short_price:.2f} x {quantity:.2f}")
            
            # 포지션 모니터링
            if self.strategy.current_position:
                current_etf_price = etf_long_price if self.strategy.current_position == "LONG" else etf_short_price
                
                # 손절/익절 확인
                exit_reason = self.strategy.check_stop_loss_take_profit(current_etf_price)
                
                if exit_reason:
                    # 손절인 경우 전환 매매
                    if exit_reason == "STOP_LOSS" and self.strategy.params.get("reverse_trigger", True):
                        if self.strategy.can_reverse():
                            result = self.strategy.execute_reversal(
                                original_symbol=original_symbol,
                                etf_long=etf_long,
                                etf_short=etf_short,
                                original_data=original_current_data,
                                etf_long_price=etf_long_price,
                                etf_short_price=etf_short_price,
                                reason=f"손절 전환 ({exit_reason})"
                            )
                            if result:
                                print(f"🔄 [{current_time.strftime('%Y-%m-%d %H:%M')}] 전환 매매: {result['from_etf']} -> {result['to_etf']}")
                        else:
                            # 전환 불가 시 청산
                            self._close_position(current_time, current_etf_price, exit_reason)
                    else:
                        # 익절인 경우 청산
                        self._close_position(current_time, current_etf_price, exit_reason)
                
                # 최대 보유 기간 확인
                elif self.strategy.check_max_hold_days2(current_time):
                    self._close_position(current_time, current_etf_price, "FORCE_CLOSE")
            
            # 자본 추적
            if self.strategy.current_position and self.strategy.entry_price:
                if self.strategy.current_position == "LONG":
                    current_etf_price = etf_long_price
                    pnl_pct = ((current_etf_price - self.strategy.entry_price) / self.strategy.entry_price) * 100
                else:
                    current_etf_price = etf_short_price
                    pnl_pct = ((self.strategy.entry_price - current_etf_price) / self.strategy.entry_price) * 100
                
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
            'total_pnl': self.strategy.capital - self.strategy.initial_capital
        }
    
    def _close_position(self, exit_time, exit_price: float, reason: str):
        """포지션 청산"""
        if not self.strategy.current_position or not self.strategy.entry_price:
            return
        
        if self.strategy.current_position == "LONG":
            pnl_pct = ((exit_price - self.strategy.entry_price) / self.strategy.entry_price) * 100
        else:
            pnl_pct = ((self.strategy.entry_price - exit_price) / self.strategy.entry_price) * 100
        
        pnl = self.strategy.entry_quantity * self.strategy.entry_price * (pnl_pct / 100)
        self.strategy.capital += self.strategy.entry_quantity * self.strategy.entry_price + pnl
        
        trade_record = {
            'entry_time': self.strategy.entry_time,
            'exit_time': exit_time,
            'symbol': self.strategy.current_etf_symbol,
            'side': self.strategy.current_position,
            'entry_price': self.strategy.entry_price,
            'exit_price': exit_price,
            'quantity': self.strategy.entry_quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        }
        self.strategy.trade_history.append(trade_record)
        
        print(f"🔒 [{exit_time.strftime('%Y-%m-%d %H:%M')}] {self.strategy.current_etf_symbol} {self.strategy.current_position} 청산 @ ${exit_price:.2f} (손익: {pnl_pct:.2f}%) - {reason}")
        
        # 포지션 초기화
        self.strategy.current_position = None
        self.strategy.current_etf_symbol = None
        self.strategy.entry_price = None
        self.strategy.entry_time = None
        self.strategy.entry_quantity = None
    
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
        
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
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

    target_item_index = 0
    # 전략 파라미터 설정
    params = REVERSAL_STRATEGY_PARAMS.copy()
    params["symbol"] = TARGET_SYMBOLS[target_item_index]["ORIGINAL"]
    params["capital"] = 12000
    params["reverse_trigger"] = True
    params["reverse_mode"] = "full"
    
    backtester = ReversalBacktester(params=params)
    
    # 백테스트 설정
    target_item = TARGET_SYMBOLS[target_item_index]
    original_symbol = target_item["ORIGINAL"]
    etf_long = target_item["LONG"]
    etf_short = target_item["SHORT"]
    
    start_date = "2024-11-01"
    end_date = "2025-11-29"
    interval = "2m"
    
    print(f"\n🚀 전환 매매 전략 백테스트 시작")
    print(f"   원본 주식: {original_symbol}")
    print(f"   롱 ETF: {etf_long}")
    print(f"   숏 ETF: {etf_short}")
    print(f"   기간: {start_date} ~ {end_date}")
    print(f"   간격: {interval}\n")
    
    results = backtester.run_backtest(
        original_symbol=original_symbol,
        etf_long=etf_long,
        etf_short=etf_short,
        start_date=start_date,
        end_date=end_date,
        interval=interval
    )
    
    if results:
        print(f"\n✅ 백테스트 완료!")
        print(f"   총 거래: {len(results['trades'])}회")
        print(f"   전환 매매: {len(results['reversals'])}회")
        print(f"   최종 자본: ${results['final_capital']:,.2f}")
        print(f"   총 손익: ${results['total_pnl']:,.2f}\n")

if __name__ == "__main__":
    main()
    print("백테스트 완료")
