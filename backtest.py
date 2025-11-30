"""
백테스트 실행 스크립트
"""
import sys
import os
from datetime import datetime, timedelta
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, INITIAL_CAPITAL_MIN
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
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1h"
    ):
        """
        백테스트 실행
        
        Args:
            symbol: 거래 심볼
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD)
            interval: 데이터 간격 (1h, 1d 등)
        """
        print(f"\n{'='*60}")
        print(f"백테스트 시작: {symbol}")
        print(f"기간: {start_date} ~ {end_date}")
        print(f"초기 자본: ${self.initial_capital:.2f}")
        print(f"{'='*60}\n")
        
        # 과거 데이터 가져오기
        print("과거 데이터 수집 중...")
        ticker = self.data_fetcher.get_historical_data(
            symbol, 
            period="max",  # 최대 기간
            interval=interval
        )
        
        if ticker is None or ticker.empty:
            print(f"❌ {symbol} 데이터 수집 실패")
            return None
        
        # 날짜 필터링
        ticker.index = pd.to_datetime(ticker.index)
        mask = (ticker.index >= start_date) & (ticker.index <= end_date)
        data = ticker.loc[mask].copy()
        
        if data.empty:
            print(f"❌ 지정된 기간에 데이터가 없습니다")
            return None
        
        print(f"✅ 데이터 수집 완료: {len(data)}개 캔들\n")
        
        # 백테스트 실행
        trader = Trader(initial_capital=self.initial_capital)
        trader.dry_run = True  # 백테스트 모드
        
        current_position = None
        entry_price = None
        entry_time = None
        entry_quantity = None  # 포지션 수량 저장
        current_capital = self.initial_capital
        
        for i in range(50, len(data)):  # 지표 계산을 위해 50개 이후부터
            current_data = data.iloc[:i+1]
            current_price = data['close'].iloc[i]
            current_time = data.index[i]
            
            # 신호 생성
            signal_data = self.signal_generator.generate_signal(
                current_data,
                current_position
            )
            
            signal = signal_data['signal']
            confidence = signal_data['confidence']
            
            # 거래 실행
            if signal == SignalType.BUY and confidence > 0.5:
                if current_position != "LONG":
                    # 기존 포지션 청산
                    if current_position == "SHORT" and entry_price and entry_quantity:
                        pnl_pct = ((entry_price - current_price) / entry_price) * 100
                        pnl = entry_quantity * entry_price * (pnl_pct / 100)
                        current_capital += entry_quantity * entry_price + pnl  # 원금 + 손익
                        self.trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'symbol': symbol,
                            'side': 'SHORT',
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'quantity': entry_quantity,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct
                        })
                    
                    # 롱 포지션 진입
                    quantity = trader.calculate_position_size(current_price, current_capital)
                    if quantity > 0:
                        trade_amount = current_price * quantity
                        current_capital -= trade_amount  # 자본 차감
                        current_position = "LONG"
                        entry_price = current_price
                        entry_time = current_time
                        entry_quantity = quantity
                        print(f"📈 [{current_time.strftime('%Y-%m-%d %H:%M')}] 롱 진입 @ ${current_price:.2f} x {quantity:.2f} (신뢰도: {confidence:.2f})")
            
            elif signal == SignalType.SELL and confidence > 0.5:
                if current_position != "SHORT":
                    # 기존 포지션 청산
                    if current_position == "LONG" and entry_price and entry_quantity:
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                        pnl = entry_quantity * entry_price * (pnl_pct / 100)
                        current_capital += entry_quantity * entry_price + pnl  # 원금 + 손익
                        self.trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'symbol': symbol,
                            'side': 'LONG',
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'quantity': entry_quantity,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct
                        })
                    
                    # 숏 포지션 진입 (숏은 자본을 차감하지 않지만, 마진을 고려)
                    quantity = trader.calculate_position_size(current_price, current_capital)
                    if quantity > 0:
                        # 숏 포지션은 마진만 차감 (간단히 거래 금액의 일부만 차감)
                        trade_amount = current_price * quantity
                        current_capital -= trade_amount  # 마진으로 자본 차감
                        current_position = "SHORT"
                        entry_price = current_price
                        entry_time = current_time
                        entry_quantity = quantity
                        print(f"📉 [{current_time.strftime('%Y-%m-%d %H:%M')}] 숏 진입 @ ${current_price:.2f} x {quantity:.2f} (신뢰도: {confidence:.2f})")
            
            # 포지션 모니터링 (손절/익절 체크)
            if current_position and entry_price and entry_quantity:
                if current_position == "LONG":
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    # 손절: -3%, 익절: +6%
                    if pnl_pct <= -3.0 or pnl_pct >= 6.0:
                        pnl = entry_quantity * entry_price * (pnl_pct / 100)
                        current_capital += entry_quantity * entry_price + pnl  # 원금 + 손익
                        self.trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'symbol': symbol,
                            'side': 'LONG',
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'quantity': entry_quantity,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct
                        })
                        print(f"🔒 [{current_time.strftime('%Y-%m-%d %H:%M')}] 롱 청산 @ ${current_price:.2f} (손익: {pnl_pct:.2f}%)")
                        current_position = None
                        entry_price = None
                        entry_time = None
                        entry_quantity = None
                
                elif current_position == "SHORT":
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                    # 손절: -3%, 익절: +6%
                    if pnl_pct <= -3.0 or pnl_pct >= 6.0:
                        pnl = entry_quantity * entry_price * (pnl_pct / 100)
                        current_capital += entry_quantity * entry_price + pnl  # 원금 + 손익
                        self.trades.append({
                            'entry_time': entry_time,
                            'exit_time': current_time,
                            'symbol': symbol,
                            'side': 'SHORT',
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'quantity': entry_quantity,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct
                        })
                        print(f"🔒 [{current_time.strftime('%Y-%m-%d %H:%M')}] 숏 청산 @ ${current_price:.2f} (손익: {pnl_pct:.2f}%)")
                        current_position = None
                        entry_price = None
                        entry_time = None
                        entry_quantity = None
            
            # 자본 추적 (미청산 포지션의 평가 손익 포함)
            if current_position and entry_price and entry_quantity:
                if current_position == "LONG":
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    pnl = entry_quantity * entry_price * (pnl_pct / 100)
                    estimated_capital = current_capital + entry_quantity * entry_price + pnl
                else:  # SHORT
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                    pnl = entry_quantity * entry_price * (pnl_pct / 100)
                    estimated_capital = current_capital + entry_quantity * entry_price + pnl
            else:
                estimated_capital = current_capital
            
            self.equity_curve.append({
                'time': current_time,
                'capital': estimated_capital
            })
        
        # 마지막 포지션 청산
        if current_position and entry_price and entry_quantity:
            final_price = data['close'].iloc[-1]
            final_time = data.index[-1]
            if current_position == "LONG":
                pnl_pct = ((final_price - entry_price) / entry_price) * 100
                pnl = entry_quantity * entry_price * (pnl_pct / 100)
            else:
                pnl_pct = ((entry_price - final_price) / entry_price) * 100
                pnl = entry_quantity * entry_price * (pnl_pct / 100)
            
            current_capital += entry_quantity * entry_price + pnl
            self.trades.append({
                'entry_time': entry_time,
                'exit_time': final_time,
                'symbol': symbol,
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
    symbol = TARGET_SYMBOLS[2] # 첫 번째 심볼
    start_date = "2024-01-01"   # 시작 날짜
    end_date = "2025-11-29"     # 종료 날짜
    interval = "1h"              # 데이터 간격
    
    # 백테스트 실행
    print(f"\n🚀 백테스트 시작")
    print(f"   심볼: {symbol}")
    print(f"   기간: {start_date} ~ {end_date}")
    print(f"   간격: {interval}")
    print(f"   초기 자본: ${INITIAL_CAPITAL_MIN:,.2f}\n")
    
    results = backtester.run_backtest(symbol, start_date, end_date, interval)
    
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