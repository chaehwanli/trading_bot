"""
파라미터 최적화 스크립트
손절/익절 비율의 최적값을 찾기 위한 그리드 서치
"""
import sys
import os
import json
from datetime import datetime
import pandas as pd
from itertools import product

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, REVERSAL_STRATEGY_PARAMS
from reversal_backtest import ReversalBacktester
from utils.logger import logger

def optimize_parameters(
    source="yfinance",
    start_date=None,
    end_date=None,
    test_symbols=None,
    interval="1h"
):
    """
    파라미터 그리드 서치를 통한 최적화
    
    Args:
        source: 데이터 소스 ("kis" or "yfinance")
        start_date: 백테스트 시작일 (None이면 전체 데이터)
        end_date: 백테스트 종료일 (None이면 전체 데이터)
        test_symbols: 테스트할 심볼 리스트 (None이면 전체)
        interval: 데이터 간격
    """
    
    # 테스트할 파라미터 범위 정의
    param_grid = {
        "1x_stop_loss": [-0.03, -0.05, -0.08],
        "2x_stop_loss": [-0.05, -0.08, -0.10],
        "take_profit": [0.10, 0.15, 0.20, 0.25, 0.30, 0.35],
    }
    
    # 테스트할 심볼 선택 (전체는 시간이 오래 걸리므로 샘플링)
    if test_symbols is None:
        # 대표적인 심볼 몇 개만 선택
        test_symbols = [
            TARGET_SYMBOLS[1],  # TSLA
            TARGET_SYMBOLS[3],  # GOOGL
            TARGET_SYMBOLS[4],  # AAPL
        ]
    else:
        test_symbols = [s for s in TARGET_SYMBOLS if s["ORIGINAL"] in test_symbols]
    
    # 날짜 범위 설정
    if start_date is None or end_date is None:
        from backtester.engine import prepare_dataset
        try:
            sample_data = prepare_dataset(test_symbols[0]["ORIGINAL"], interval, source=source)
            if start_date is None:
                start_date = sample_data.index.min().strftime("%Y-%m-%d")
            if end_date is None:
                end_date = sample_data.index.max().strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"Could not read date range: {e}")
            return
    
    logger.info(f"Starting parameter optimization")
    logger.info(f"Source: {source}")
    logger.info(f"Period: {start_date} to {end_date}")
    logger.info(f"Testing {len(test_symbols)} symbols")
    logger.info(f"Parameter grid: {param_grid}")
    
    # 모든 파라미터 조합 생성
    param_combinations = list(product(
        param_grid["1x_stop_loss"],
        param_grid["2x_stop_loss"],
        param_grid["take_profit"]
    ))
    
    logger.info(f"Total combinations to test: {len(param_combinations)}")
    
    results = []
    
    # 각 파라미터 조합에 대해 백테스트 실행
    for idx, (stop_1x, stop_2x, take_profit) in enumerate(param_combinations, 1):
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing combination {idx}/{len(param_combinations)}")
        logger.info(f"1X Stop Loss: {stop_1x:.1%}, 2X Stop Loss: {stop_2x:.1%}, Take Profit: {take_profit:.1%}")
        logger.info(f"{'='*70}")
        
        total_pnl = 0
        total_trades = 0
        total_fee = 0
        
        # 상세 통계용 변수
        stats = {
            "LONG": {"count": 0, "wins": 0, "losses": 0, "pnl": 0, "win_pnl": 0, "loss_pnl": 0, "stop_loss": 0, "take_profit": 0, "force_close_win": 0, "force_close_loss": 0},
            "SHORT": {"count": 0, "wins": 0, "losses": 0, "pnl": 0, "win_pnl": 0, "loss_pnl": 0, "stop_loss": 0, "take_profit": 0, "force_close_win": 0, "force_close_loss": 0}
        }
        
        # 각 심볼에 대해 백테스트
        for target_item in test_symbols:
            original_symbol = target_item["ORIGINAL"]
            etf_long = target_item["LONG"]
            etf_long_multiple = target_item["LONG_MULTIPLE"]
            etf_short = target_item["SHORT"]
            etf_short_multiple = target_item["SHORT_MULTIPLE"]
            
            # 파라미터 설정
            params = REVERSAL_STRATEGY_PARAMS.copy()
            params["symbol"] = original_symbol
            params["capital"] = 2300
            params["1x_stop_loss_rate"] = stop_1x
            params["2x_stop_loss_rate"] = stop_2x
            params["take_profit_rate"] = take_profit
            params["reverse_trigger"] = False
            
            try:
                backtester = ReversalBacktester(params=params, source=source)
                
                result = backtester.run_backtest(
                    original_symbol=original_symbol,
                    etf_long=etf_long,
                    etf_long_multiple=etf_long_multiple,
                    etf_short=etf_short,
                    etf_short_multiple=etf_short_multiple,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval
                )
                
                if result:
                    trades = result.get('trades', [])
                    total_pnl += result.get('total_pnl', 0)
                    total_trades += len(trades)
                    total_fee += result.get('total_fee', 0)
                    
                    for t in trades:
                        side = t['side'] # 'LONG' or 'SHORT'
                        pnl = t['pnl']
                        reason = t['reason']
                        
                        stats[side]["count"] += 1
                        stats[side]["pnl"] += pnl
                        
                        if pnl > 0:
                            stats[side]["wins"] += 1
                            stats[side]["win_pnl"] += pnl
                            if reason == "TAKE_PROFIT":
                                stats[side]["take_profit"] += 1
                            elif reason == "FORCE_CLOSE_TRADING_DAY_LIMIT":
                                stats[side]["force_close_win"] += 1
                        else:
                            stats[side]["losses"] += 1
                            stats[side]["loss_pnl"] += pnl
                            if reason == "STOP_LOSS":
                                stats[side]["stop_loss"] += 1
                            elif reason == "FORCE_CLOSE_TRADING_DAY_LIMIT":
                                stats[side]["force_close_loss"] += 1
                                
            except Exception as e:
                logger.error(f"Error testing {original_symbol}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # 결과 계산
        total_wins = stats["LONG"]["wins"] + stats["SHORT"]["wins"]
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        avg_pnl = total_pnl / len(test_symbols) if test_symbols else 0
        
        long_win_rate = (stats["LONG"]["wins"] / stats["LONG"]["count"]) if stats["LONG"]["count"] > 0 else 0
        short_win_rate = (stats["SHORT"]["wins"] / stats["SHORT"]["count"]) if stats["SHORT"]["count"] > 0 else 0
        
        avg_long_win = (stats["LONG"]["win_pnl"] / stats["LONG"]["wins"]) if stats["LONG"]["wins"] > 0 else 0
        avg_long_loss = (stats["LONG"]["loss_pnl"] / stats["LONG"]["losses"]) if stats["LONG"]["losses"] > 0 else 0
        avg_short_win = (stats["SHORT"]["win_pnl"] / stats["SHORT"]["wins"]) if stats["SHORT"]["wins"] > 0 else 0
        avg_short_loss = (stats["SHORT"]["loss_pnl"] / stats["SHORT"]["losses"]) if stats["SHORT"]["losses"] > 0 else 0
        
        res_entry = {
            "1x_stop_loss": stop_1x,
            "2x_stop_loss": stop_2x,
            "take_profit": take_profit,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "win_rate": win_rate,
            "total_trades": int(total_trades),
            "total_fee": total_fee,
            
            "long_trades": int(stats["LONG"]["count"]),
            "long_win_rate": long_win_rate * 100,
            "long_avg_profit": avg_long_win,
            "long_avg_loss": avg_long_loss,
            "long_stop_loss": int(stats["LONG"]["stop_loss"]),
            "long_fc_loss": int(stats["LONG"]["force_close_loss"]),
            "long_take_profit": int(stats["LONG"]["take_profit"]),
            "long_fc_win": int(stats["LONG"]["force_close_win"]),
            
            "short_trades": int(stats["SHORT"]["count"]),
            "short_win_rate": short_win_rate * 100,
            "short_avg_profit": avg_short_win,
            "short_avg_loss": avg_short_loss,
            "short_stop_loss": int(stats["SHORT"]["stop_loss"]),
            "short_fc_loss": int(stats["SHORT"]["force_close_loss"]),
            "short_take_profit": int(stats["SHORT"]["take_profit"]),
            "short_fc_win": int(stats["SHORT"]["force_close_win"]),
        }
        results.append(res_entry)
        
        logger.info(f"Result: PnL=${total_pnl:.2f}, Win={win_rate/100:.1%} ({total_wins}/{total_trades}), Fee=${total_fee:.2f}")
        logger.info(f" LONG: Trades={stats['LONG']['count']}, Win={long_win_rate:.1%}, AvgP=${avg_long_win:.2f}, AvgL=${avg_long_loss:.2f}")
        logger.info(f"       Exit L: SL={stats['LONG']['stop_loss']}, FC_L={stats['LONG']['force_close_loss']} | Exit P: TP={stats['LONG']['take_profit']}, FC_P={stats['LONG']['force_close_win']}")
        logger.info(f" SHORT: Trades={stats['SHORT']['count']}, Win={short_win_rate:.1%}, AvgP=${avg_short_win:.2f}, AvgL=${avg_short_loss:.2f}")
        logger.info(f"       Exit L: SL={stats['SHORT']['stop_loss']}, FC_L={stats['SHORT']['force_close_loss']} | Exit P: TP={stats['SHORT']['take_profit']}, FC_P={stats['SHORT']['force_close_win']}")
    
    # 결과를 DataFrame으로 변환
    df_results = pd.DataFrame(results)
    
    # 결과 정렬 (총 수익 기준)
    df_results = df_results.sort_values("total_pnl", ascending=False)
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"optimization_results_{source}_{timestamp}.csv"
    df_results.to_csv(output_file, index=False)
    logger.info(f"\nResults saved to {output_file}")
    
    # 상위 50개 결과 출력
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print("\n" + "="*160)
    print("TOP 50 PARAMETER COMBINATIONS")
    print("="*160)
    # 필요한 컬럼만 선택해서 출력
    display_cols = [
        "1x_stop_loss", "2x_stop_loss", "take_profit", "total_pnl", "win_rate", "total_trades", "total_fee",
        "long_win_rate", "short_win_rate", "long_avg_profit", "long_avg_loss", "short_avg_profit", "short_avg_loss"
    ]
    print(df_results[display_cols].head(50).to_string(index=False))
    
    # 최적 파라미터 출력
    best = df_results.iloc[0]
    print("\n" + "="*100)
    print("BEST PARAMETERS")
    print("="*100)
    print(f"1X Stop Loss/2X/TP: {best['1x_stop_loss']:.1%}/{best['2x_stop_loss']:.1%}/{best['take_profit']:.1%}")
    print(f"Total PnL/Fee:      ${best['total_pnl']:.2f} / ${best['total_fee']:.2f}")
    print(f"Win Rate (T/L/S):   {best['win_rate']:.1f}% / {best['long_win_rate']:.1f}% / {best['short_win_rate']:.1f}%")
    print(f"Total Trades (L/S): {int(best['total_trades'])} ({int(best['long_trades'])}/{int(best['short_trades'])})")
    print(f"Long Avg P/L:       ${best['long_avg_profit']:.2f} / ${best['long_avg_loss']:.2f}")
    print(f"Short Avg P/L:      ${best['short_avg_profit']:.2f} / ${best['short_avg_loss']:.2f}")
    print(f"Exit (Long):        SL={int(best['long_stop_loss'])}, TP={int(best['long_take_profit'])}, FC_L={int(best['long_fc_loss'])}, FC_P={int(best['long_fc_win'])}")
    print(f"Exit (Short):       SL={int(best['short_stop_loss'])}, TP={int(best['short_take_profit'])}, FC_L={int(best['short_fc_loss'])}, FC_P={int(best['short_fc_win'])}")
    print("="*100)
    
    # 설정 파일 업데이트 제안
    print("\nTo update settings.py, use these values:")
    print(f"REVERSAL_1X_STOP_LOSS_RATE = {best['1x_stop_loss']}")
    print(f"REVERSAL_2X_STOP_LOSS_RATE = {best['2x_stop_loss']}")
    print(f"REVERSAL_TAKE_PROFIT_RATE = {best['take_profit']}")
    
    return df_results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimize trading strategy parameters")
    parser.add_argument("--source", type=str, choices=["kis", "yfinance"], default="yfinance", help="Data source")
    parser.add_argument("--start-date", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--symbols", nargs="+", default=None, help="Symbols to test (default: TSLA, GOOGL, AAPL)")
    
    args = parser.parse_args()
    
    results = optimize_parameters(
        source=args.source,
        start_date=args.start_date,
        end_date=args.end_date,
        test_symbols=args.symbols
    )
