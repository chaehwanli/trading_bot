"""
RSI 진입 임계값 최적화 스크립트
RSI Oversold 기준값을 변경하며 수익률과 거래 횟수 변화를 분석
"""
import sys
import os
import pandas as pd
from datetime import datetime
from itertools import product

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, REVERSAL_STRATEGY_PARAMS
from reversal_backtest import ReversalBacktester
from utils.logger import logger

def optimize_rsi(source="kis", interval="1h"):
    # 테스트할 RSI Oversold 임계값 범위
    # 기존: 30 (logic uses +10 so 40)
    # 제안: 45, 50, 55 등 테스트
    # 입력값은 SignalGenerator에서 직접 비교값으로 사용됨 (수정된 로직 기준)
    rsi_thresholds = [30, 35, 40, 45, 50, 55, 60, 65]
    
    # 고정 파라미터 (이전 최적화 결과)
    fixed_params = {
        "1x_stop_loss_rate": -0.03,
        "2x_stop_loss_rate": -0.08,
        "take_profit_rate": 0.35,
        "long_max_hold_days": 5,
        "short_max_hold_days": 1,
    }
    
    # 테스트 심볼 (TSLA, NVDA 등 변동성 큰 종목 위주)
    test_symbols = [
        # TARGET_SYMBOLS[1],  # TSLA (index might vary, better filter by name)
        next(item for item in TARGET_SYMBOLS if item["ORIGINAL"] == "TSLA"),
        next(item for item in TARGET_SYMBOLS if item["ORIGINAL"] == "NVDA"),
        # next(item for item in TARGET_SYMBOLS if item["ORIGINAL"] == "SOXL"), # If exists
    ]
    
    logger.info(f"Starting RSI Optimization")
    logger.info(f"RSI Thresholds: {rsi_thresholds}")
    logger.info(f"Fixed Params: {fixed_params}")
    
    results = []
    
    for rsi_val in rsi_thresholds:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing RSI Oversold Threshold: < {rsi_val}")
        logger.info(f"{'='*60}")
        
        total_pnl = 0
        total_trades = 0
        total_wins = 0
        
        for target_item in test_symbols:
            original_symbol = target_item["ORIGINAL"]
            etf_long = target_item["LONG"]
            etf_long_multiple = target_item["LONG_MULTIPLE"]
            etf_short = target_item["SHORT"]
            etf_short_multiple = target_item["SHORT_MULTIPLE"]
            
            # 파라미터 설정
            params = REVERSAL_STRATEGY_PARAMS.copy()
            params["symbol"] = original_symbol
            params["capital"] = 2300 # 충분한 자본
            params.update(fixed_params)
            params["rsi_oversold"] = rsi_val  # 핵심: RSI 임계값 주입
            params["reverse_trigger"] = False
            
            try:
                # Use "kis" source as default for reliability if available, else yfinance
                backtester = ReversalBacktester(params=params, source=source)
                
                # 기간은 최근 1년 ~ 2년 (데이터 파일에 따라 다름)
                result = backtester.run_backtest(
                    original_symbol=original_symbol,
                    etf_long=etf_long,
                    etf_long_multiple=etf_long_multiple,
                    etf_short=etf_short,
                    etf_short_multiple=etf_short_multiple,
                    start_date="2024-01-01", 
                    end_date=datetime.now().strftime("%Y-%m-%d"), 
                    interval=interval
                )
                
                if result:
                    trades = result.get('trades', [])
                    pnl = result.get('total_pnl', 0)
                    
                    total_pnl += pnl
                    total_trades += len(trades)
                    wins = len([t for t in trades if t['pnl'] > 0])
                    total_wins += wins
                    
                    logger.info(f" {original_symbol}: PnL=${pnl:.2f}, Trades={len(trades)}, WinRate={wins/len(trades)*100 if trades else 0:.1f}%")
            
            except Exception as e:
                logger.error(f"Error testing {original_symbol} with RSI {rsi_val}: {e}")
                continue
        
        # 합계 결과
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        avg_pnl_per_trade = (total_pnl / total_trades) if total_trades > 0 else 0
        
        res_entry = {
            "rsi_threshold": rsi_val,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_pnl_per_trade": avg_pnl_per_trade
        }
        results.append(res_entry)
        logger.info(f"RSI {rsi_val} Result: Total PnL=${total_pnl:.2f}, Trades={total_trades}, WinRate={win_rate:.1f}%")

    # 결과 출력 및 저장
    df = pd.DataFrame(results)
    df = df.sort_values("total_pnl", ascending=False)
    
    print("\n" + "="*80)
    print("RSI OPTIMIZATION RESULTS")
    print("="*80)
    print(df.to_string(index=False))
    
    # CSV 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    df.to_csv(f"rsi_optimization_results_{timestamp}.csv", index=False)
    
    # Best
    best = df.iloc[0]
    print(f"\nBest RSI Threshold: {int(best['rsi_threshold'])}")
    print(f"PnL: ${best['total_pnl']:.2f}, Trades: {int(best['total_trades'])}")

if __name__ == "__main__":
    optimize_rsi(source="yfinance")
