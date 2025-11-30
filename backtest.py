"""
백테스트 실행 스크립트
"""
import sys
import os
from datetime import datetime, timedelta
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, INITIAL_CAPITAL_MIN, STOP_LOSS, TAKE_PROFIT, get_etf_by_original
from data.data_fetcher import DataFetcher
from strategy.signal_generator import SignalGenerator, SignalType
from trading.trader import Trader
from utils.logger import logger

class Backtester:
    """백테스트 클래스"""
    
    def __init__(self, initial_capital: float = 2000.0):
        self.data_fetcher = DataFetcher()
        self.signal_generator = SignalGenerator()
        self.initial_capital = initial_capital
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
        백테스트 실행 - 원본 주식 분석 후 ETF 스위칭
        
        Args:
            original_symbol: 원본 주식 심볼 (예: "TSLA")
            etf_long: 롱 ETF 심볼 (예: "TSLL")
            etf_short: 숏 ETF 심볼 (예: "TSLZ")
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD)
            interval: 데이터 간격 (1h, 1d 등)
        """
        print(f"\n{'='*60}")
        print(f"백테스트 시작: {original_symbol} -> {etf_long}/{etf_short} 스위칭")
        print(f"기간: {start_date} ~ {end_date}")
        print(f"초기 자본: ${self.initial_capital:.2f}")
        print(f"{'='*60}\n")
        
        # 원본 주식 데이터 가져오기 (신호 생성용)
        print(f"원본 주식({original_symbol}) 데이터 수집 중...")
        original_data = self.data_fetcher.get_historical_data(
            original_symbol, 
            period="max",
            interval=interval
        )
        
        if original_data is None or original_data.empty:
            print(f"❌ {original_symbol} 데이터 수집 실패")
            return None
        
        # ETF 데이터 가져오기 (가격 조회용)
        print(f"롱 ETF({etf_long}) 데이터 수집 중...")
        etf_long_data = self.data_fetcher.get_historical_data(
            etf_long,
            period="max",
            interval=interval
        )
        
        print(f"숏 ETF({etf_short}) 데이터 수집 중...")
        etf_short_data = self.data_fetcher.get_historical_data(
            etf_short,
            period="max",
            interval=interval
        )
        
        if etf_long_data is None or etf_long_data.empty or etf_short_data is None or etf_short_data.empty:
            print(f"❌ ETF 데이터 수집 실패")
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
            print(f"❌ 지정된 기간에 데이터가 없습니다")
            return None
        
        print(f"✅ 데이터 수집 완료: 원본 {len(original_data)}개, 롱 {len(etf_long_data)}개, 숏 {len(etf_short_data)}개 캔들\n")
        
        # 백테스트 실행
        trader = Trader(initial_capital=self.initial_capital)
        trader.dry_run = True  # 백테스트 모드
        
        current_position = None  # "LONG" or "SHORT" or None
        current_etf_symbol = None  # 현재 보유 중인 ETF 심볼 (etf_long or etf_short)
        entry_price = None
        entry_time = None
        entry_quantity = None
        current_capital = self.initial_capital
        
        # 데이터 인덱스 정렬 (시간 기준으로 맞춤)
        common_index = original_data.index.intersection(etf_long_data.index).intersection(etf_short_data.index)
        common_index = common_index.sort_values()
        
        for i in range(50, len(common_index)):  # 지표 계산을 위해 50개 이후부터
            current_time = common_index[i]
            
            # 원본 주식 데이터 (신호 생성용) - 현재 시간까지의 데이터
            original_mask = original_data.index <= current_time
            original_current_data = original_data.loc[original_mask]
            
            if len(original_current_data) < 50:
                continue
            
            # ETF 가격 조회 - 가장 가까운 시간의 가격
            try:
                etf_long_price = etf_long_data.loc[etf_long_data.index <= current_time, 'close'].iloc[-1]
                etf_short_price = etf_short_data.loc[etf_short_data.index <= current_time, 'close'].iloc[-1]
            except (IndexError, KeyError):
                continue
            
            # 원본 주식으로 신호 생성
            signal_data = self.signal_generator.generate_signal(
                original_current_data,
                current_position
            )
            
            signal = signal_data['signal']
            confidence = signal_data['confidence']
            
            # BUY 신호 → TSLL(롱 ETF) 진입
            if signal == SignalType.BUY and confidence > 0.5:
                if current_position != "LONG":
                    # 기존 포지션 청산 (TSLZ 숏 포지션이 있으면 청산)
                    if current_position == "SHORT" and current_etf_symbol == etf_short and entry_price and entry_quantity:
                        current_etf_price = etf_short_price
                        pnl_pct = ((entry_price - current_etf_price) / entry_price) * 100
                        pnl = entry_quantity * entry_price * (pnl_pct / 100)
                        current_capital += entry_quantity * entry_price + pnl
                        self.trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'symbol': current_etf_symbol,
                            'side': 'SHORT',
                            'entry_price': entry_price,
                            'exit_price': current_etf_price,
                            'quantity': entry_quantity,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct
                        })
                        print(f"🔄 [{current_time.strftime('%Y-%m-%d %H:%M')}] {current_etf_symbol} 숏 청산 @ ${current_etf_price:.2f} (손익: {pnl_pct:.2f}%)")
                    
                    # TSLL(롱 ETF) 진입
                    current_etf_price = etf_long_price
                    quantity = trader.calculate_position_size(current_etf_price, current_capital)
                    if quantity > 0:
                        trade_amount = current_etf_price * quantity
                        current_capital -= trade_amount
                        current_position = "LONG"
                        current_etf_symbol = etf_long
                        entry_price = current_etf_price
                        entry_time = current_time
                        entry_quantity = quantity
                        print(f"📈 [{current_time.strftime('%Y-%m-%d %H:%M')}] {original_symbol} -> {etf_long} 롱 진입 @ ${current_etf_price:.2f} x {quantity:.2f} (신뢰도: {confidence:.2f})")
            
            # SELL 신호 → TSLZ(숏 ETF) 진입
            elif signal == SignalType.SELL and confidence > 0.5:
                if current_position != "SHORT":
                    # 기존 포지션 청산 (TSLL 롱 포지션이 있으면 청산)
                    if current_position == "LONG" and current_etf_symbol == etf_long and entry_price and entry_quantity:
                        current_etf_price = etf_long_price
                        pnl_pct = ((current_etf_price - entry_price) / entry_price) * 100
                        pnl = entry_quantity * entry_price * (pnl_pct / 100)
                        current_capital += entry_quantity * entry_price + pnl
                        self.trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'symbol': current_etf_symbol,
                            'side': 'LONG',
                            'entry_price': entry_price,
                            'exit_price': current_etf_price,
                            'quantity': entry_quantity,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct
                        })
                        print(f"🔄 [{current_time.strftime('%Y-%m-%d %H:%M')}] {current_etf_symbol} 롱 청산 @ ${current_etf_price:.2f} (손익: {pnl_pct:.2f}%)")
                    
                    # TSLZ(숏 ETF) 진입
                    current_etf_price = etf_short_price
                    quantity = trader.calculate_position_size(current_etf_price, current_capital)
                    if quantity > 0:
                        trade_amount = current_etf_price * quantity
                        current_capital -= trade_amount
                        current_position = "SHORT"
                        current_etf_symbol = etf_short
                        entry_price = current_etf_price
                        entry_time = current_time
                        entry_quantity = quantity
                        print(f"📉 [{current_time.strftime('%Y-%m-%d %H:%M')}] {original_symbol} -> {etf_short} 숏 진입 @ ${current_etf_price:.2f} x {quantity:.2f} (신뢰도: {confidence:.2f})")
            
            # 포지션 모니터링 (손절/익절 체크)
            if current_position and current_etf_symbol and entry_price and entry_quantity:
                # 현재 보유 중인 ETF 가격 조회
                if current_position == "LONG" and current_etf_symbol == etf_long:
                    current_etf_price = etf_long_price
                    pnl_pct = ((current_etf_price - entry_price) / entry_price) * 100
                elif current_position == "SHORT" and current_etf_symbol == etf_short:
                    current_etf_price = etf_short_price
                    pnl_pct = ((entry_price - current_etf_price) / entry_price) * 100
                else:
                    continue
                
                # 손절/익절 체크 (설정값 사용)
                if pnl_pct <= STOP_LOSS * 100 or pnl_pct >= TAKE_PROFIT * 100:
                    pnl = entry_quantity * entry_price * (pnl_pct / 100)
                    current_capital += entry_quantity * entry_price + pnl
                    self.trades.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'symbol': current_etf_symbol,
                        'side': current_position,
                        'entry_price': entry_price,
                        'exit_price': current_etf_price,
                        'quantity': entry_quantity,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })
                    print(f"🔒 [{current_time.strftime('%Y-%m-%d %H:%M')}] {current_etf_symbol} {current_position} 청산 @ ${current_etf_price:.2f} (손익: {pnl_pct:.2f}%)")
                    current_position = None
                    current_etf_symbol = None
                    entry_price = None
                    entry_time = None
                    entry_quantity = None
            
            # 자본 추적 (미청산 포지션의 평가 손익 포함)
            if current_position and current_etf_symbol and entry_price and entry_quantity:
                if current_position == "LONG" and current_etf_symbol == etf_long:
                    current_etf_price = etf_long_price
                    pnl_pct = ((current_etf_price - entry_price) / entry_price) * 100
                    pnl = entry_quantity * entry_price * (pnl_pct / 100)
                    estimated_capital = current_capital + entry_quantity * entry_price + pnl
                elif current_position == "SHORT" and current_etf_symbol == etf_short:
                    current_etf_price = etf_short_price
                    pnl_pct = ((entry_price - current_etf_price) / entry_price) * 100
                    pnl = entry_quantity * entry_price * (pnl_pct / 100)
                    estimated_capital = current_capital + entry_quantity * entry_price + pnl
                else:
                    estimated_capital = current_capital
            else:
                estimated_capital = current_capital
            
            self.equity_curve.append({
                'time': current_time,
                'capital': estimated_capital
            })
        
        # 마지막 포지션 청산
        if current_position and current_etf_symbol and entry_price and entry_quantity:
            final_time = common_index[-1]
            try:
                if current_position == "LONG" and current_etf_symbol == etf_long:
                    final_price = etf_long_data.loc[etf_long_data.index <= final_time, 'close'].iloc[-1]
                    pnl_pct = ((final_price - entry_price) / entry_price) * 100
                    pnl = entry_quantity * entry_price * (pnl_pct / 100)
                elif current_position == "SHORT" and current_etf_symbol == etf_short:
                    final_price = etf_short_data.loc[etf_short_data.index <= final_time, 'close'].iloc[-1]
                    pnl_pct = ((entry_price - final_price) / entry_price) * 100
                    pnl = entry_quantity * entry_price * (pnl_pct / 100)
                else:
                    final_price = None
                    pnl = 0
                    pnl_pct = 0
            except (IndexError, KeyError):
                final_price = None
                pnl = 0
                pnl_pct = 0
            
            if final_price:
                current_capital += entry_quantity * entry_price + pnl
                self.trades.append({
                    'entry_time': entry_time,
                    'exit_time': final_time,
                    'symbol': current_etf_symbol,
                    'side': current_position,
                    'entry_price': entry_price,
                    'exit_price': final_price,
                    'quantity': entry_quantity,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                })
            
            current_capital += entry_quantity * entry_price + pnl
            self.trades.append({
                'entry_time': entry_time,
                'exit_time': final_time,
                'symbol': current_etf_symbol,
                'side': current_position,
                'entry_price': entry_price,
                'exit_price': final_price,
                'quantity': entry_quantity,
                'pnl': pnl,
                'pnl_pct': pnl_pct
            })
        
        # 최종 자본 저장
        self.final_capital = current_capital
        
        # 결과 출력
        self._print_results()
        
        return {
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'final_capital': current_capital,
            'total_pnl': current_capital - self.initial_capital
        }
    
    def _print_results(self):
        """백테스트 결과 출력"""
        if not self.trades:
            print("\n❌ 거래가 없습니다.")
            return
        
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] < 0]
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        total_pnl_pct = (total_pnl / self.initial_capital) * 100
        
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # 최종 자본 계산
        if hasattr(self, 'final_capital'):
            final_capital = self.final_capital
        elif self.equity_curve:
            final_capital = self.equity_curve[-1]['capital']
        else:
            final_capital = self.initial_capital + total_pnl
        
        # 최대 수익/손실 거래
        max_win = max(self.trades, key=lambda x: x['pnl']) if winning_trades else None
        max_loss = min(self.trades, key=lambda x: x['pnl']) if losing_trades else None
        
        # 승률 대비 손익비 계산
        profit_factor = abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades and sum(t['pnl'] for t in losing_trades) != 0 else 0
        
        # 결과 요약 출력
        print(f"\n{'='*70}")
        print("📊 백테스트 결과 요약")
        print(f"{'='*70}")
        print(f"\n💰 자본 변화")
        print(f"  초기 자본:     ${self.initial_capital:>12,.2f}")
        print(f"  최종 자본:     ${final_capital:>12,.2f}")
        pnl_sign = "+" if total_pnl >= 0 else ""
        pnl_color = "🟢" if total_pnl >= 0 else "🔴"
        print(f"  총 손익:       {pnl_color} {pnl_sign}${total_pnl:>11,.2f} ({pnl_sign}{total_pnl_pct:>6.2f}%)")
        
        print(f"\n📈 거래 통계")
        print(f"  총 거래 횟수:  {total_trades:>12}회")
        print(f"  승리 거래:     {len(winning_trades):>12}회 ({win_rate:>6.2f}%)")
        print(f"  손실 거래:     {len(losing_trades):>12}회 ({100-win_rate:>6.2f}%)")
        
        print(f"\n💵 평균 손익")
        print(f"  평균 수익:     ${avg_win:>12,.2f}")
        print(f"  평균 손실:     ${avg_loss:>12,.2f}")
        if avg_loss != 0:
            risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            print(f"  위험/보상 비율: {risk_reward:>12.2f}")
        
        if profit_factor > 0:
            print(f"  수익 팩터:     {profit_factor:>12.2f}")
        
        if max_win:
            print(f"\n🏆 최대 수익 거래")
            print(f"  {max_win['side']} | 진입: {max_win['entry_time'].strftime('%Y-%m-%d %H:%M')} @ ${max_win['entry_price']:.2f}")
            print(f"  청산: {max_win['exit_time'].strftime('%Y-%m-%d %H:%M')} @ ${max_win['exit_price']:.2f}")
            print(f"  손익: +${max_win['pnl']:.2f} (+{max_win['pnl_pct']:.2f}%)")
        
        if max_loss:
            print(f"\n📉 최대 손실 거래")
            print(f"  {max_loss['side']} | 진입: {max_loss['entry_time'].strftime('%Y-%m-%d %H:%M')} @ ${max_loss['entry_price']:.2f}")
            print(f"  청산: {max_loss['exit_time'].strftime('%Y-%m-%d %H:%M')} @ ${max_loss['exit_price']:.2f}")
            print(f"  손익: ${max_loss['pnl']:.2f} ({max_loss['pnl_pct']:.2f}%)")
        
        print(f"\n{'='*70}\n")
        
        # 거래 내역
        print("📋 상세 거래 내역:")
        print("-" * 70)
        for i, trade in enumerate(self.trades, 1):
            pnl_sign = "+" if trade['pnl'] > 0 else ""
            pnl_emoji = "✅" if trade['pnl'] > 0 else "❌"
            print(f"{i:>3}. {pnl_emoji} {trade['side']:>5} | "
                  f"진입: {trade['entry_time'].strftime('%Y-%m-%d %H:%M'):>16} @ ${trade['entry_price']:>7.2f} | "
                  f"청산: {trade['exit_time'].strftime('%Y-%m-%d %H:%M'):>16} @ ${trade['exit_price']:>7.2f} | "
                  f"손익: {pnl_sign}${trade['pnl']:>8.2f} ({pnl_sign}{trade['pnl_pct']:>6.2f}%)")

def main():
    """백테스트 메인 함수"""
    backtester = Backtester(initial_capital=INITIAL_CAPITAL_MIN)
    
    # 백테스트 설정
    # 원본 주식 선택 (예: TSLA 또는 NVDA)
    target_item = TARGET_SYMBOLS[1] # 첫 번째 항목 (TSLA)
    original_symbol = target_item["ORIGINAL"]  # "TSLA"
    etf_long = target_item["LONG"]   # "TSLL"
    etf_short = target_item["SHORT"] # "TSLZ"
    
    # 백테스트할 ETF 선택 (LONG 또는 SHORT)
    # 원본 주식의 거래 상황을 분석하여 자동으로 선택하거나, 수동으로 지정 가능
    test_etf = etf_long  # 또는 etf_short로 변경 가능
    
    start_date = "2024-11-01"   # 시작 날짜
    end_date = "2025-11-29"     # 종료 날짜
    interval = "1h"              # 데이터 간격
    
    # 백테스트 실행
    print(f"\n🚀 백테스트 시작")
    print(f"   원본 주식: {original_symbol}")
    print(f"   테스트 ETF: {test_etf} ({'LONG' if test_etf == etf_long else 'SHORT'})")
    print(f"   기간: {start_date} ~ {end_date}")
    print(f"   간격: {interval}")
    print(f"   초기 자본: ${INITIAL_CAPITAL_MIN:,.2f}\n")
    
    # 백테스트 실행 - 원본 주식 분석 후 ETF 스위칭
    results = backtester.run_backtest(
        original_symbol=original_symbol,
        etf_long=etf_long,
        etf_short=etf_short,
        start_date=start_date,
        end_date=end_date,
        interval=interval
    )
    
    if results:
        # 최종 요약 출력
        print(f"\n{'='*70}")
        print("✅ 백테스트 완료!")
        print(f"{'='*70}")
        print(f"📊 최종 요약:")
        print(f"   총 거래: {len(results['trades'])}회")
        print(f"   최종 자본: ${results['final_capital']:,.2f}")
        print(f"   총 손익: ${results['total_pnl']:,.2f} ({results['total_pnl']/INITIAL_CAPITAL_MIN*100:.2f}%)")
        print(f"{'='*70}\n")

if __name__ == "__main__":
    main()