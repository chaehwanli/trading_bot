"""
테스트용 거래 봇
"""
import time
from datetime import datetime
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import TARGET_SYMBOLS, INITIAL_CAPITAL_MIN, DRY_RUN, get_all_etf_symbols
from data.data_fetcher import DataFetcher
from strategy.signal_generator import SignalGenerator, SignalType
from strategy.indicators import TechnicalIndicators
from trading.trader import Trader
from utils.logger import logger

def test_data_fetcher():
    """데이터 수집 테스트"""
    print("\n=== 데이터 수집 테스트 ===")
    fetcher = DataFetcher()
    
    # 첫 번째 원본 주식과 ETF 테스트
    if TARGET_SYMBOLS:
        test_item = TARGET_SYMBOLS[0]
        test_symbols = [test_item["ORIGINAL"], test_item["LONG"], test_item["SHORT"]]
    else:
        test_symbols = []
    
    for symbol in test_symbols[:1]:  # 첫 번째 심볼만 테스트
        print(f"\n{symbol} 테스트:")
        
        # 실시간 가격
        price = fetcher.get_realtime_price(symbol)
        print(f"  현재가: ${price:.2f}" if price else "  가격 조회 실패")
        
        # 과거 데이터
        data = fetcher.get_historical_data(symbol, period="1mo", interval="1h")
        if data is not None:
            print(f"  과거 데이터: {len(data)}개")
            print(f"  최신 가격: ${data['close'].iloc[-1]:.2f}")

def test_indicators():
    """기술적 지표 테스트"""
    print("\n=== 기술적 지표 테스트 ===")
    fetcher = DataFetcher()
    indicators = TechnicalIndicators()
    
    # 첫 번째 원본 주식 사용
    if TARGET_SYMBOLS:
        test_item = TARGET_SYMBOLS[0]
        symbol = test_item["ORIGINAL"]  # 원본 주식 코드
    else:
        symbol = "TSLA"  # 기본값
    data = fetcher.get_historical_data(symbol, period="1mo", interval="1h")
    
    if data is not None:
        # RSI
        rsi = indicators.get_latest_rsi(data)
        print(f"{symbol} RSI: {rsi:.2f}" if rsi else f"{symbol} RSI 계산 실패")
        
        # MACD
        macd = indicators.get_latest_macd(data)
        if macd:
            print(f"{symbol} MACD:")
            print(f"  MACD: {macd['macd']:.4f}")
            print(f"  Signal: {macd['signal']:.4f}")
            print(f"  Histogram: {macd['histogram']:.4f}")

def test_signal_generator():
    """신호 생성 테스트"""
    print("\n=== 매매 신호 생성 테스트 ===")
    fetcher = DataFetcher()
    signal_gen = SignalGenerator()
    
    # 첫 번째 원본 주식 사용
    if TARGET_SYMBOLS:
        test_item = TARGET_SYMBOLS[0]
        symbol = test_item["ORIGINAL"]  # 원본 주식 코드
    else:
        symbol = "TSLA"  # 기본값
    data = fetcher.get_intraday_data(symbol, interval="5m")
    
    if data is not None:
        signal_data = signal_gen.generate_signal(data)
        
        print(f"{symbol} 신호 분석:")
        print(f"  신호: {signal_data['signal'].value}")
        print(f"  RSI: {signal_data['rsi']:.2f}" if signal_data['rsi'] else "  RSI: N/A")
        if signal_data['macd']:
            print(f"  MACD Histogram: {signal_data['macd']['histogram']:.4f}")
        print(f"  신뢰도: {signal_data['confidence']:.2f}")
        print(f"  이유: {signal_data['reason']}")

def test_trader():
    """거래자 테스트"""
    print("\n=== 거래자 테스트 ===")
    trader = Trader(initial_capital=INITIAL_CAPITAL_MIN)
    
    print(f"초기 자본: ${trader.capital:.2f}")
    print(f"사용 가능 자본: ${trader.get_account_balance():.2f}")
    
    # 첫 번째 원본 주식 사용
    if TARGET_SYMBOLS:
        test_item = TARGET_SYMBOLS[0]
        symbol = test_item["ORIGINAL"]  # 원본 주식 코드
    else:
        symbol = "TSLA"  # 기본값
    fetcher = DataFetcher()
    price = fetcher.get_realtime_price(symbol)
    
    if price:
        quantity = trader.calculate_position_size(price)
        print(f"{symbol} @ ${price:.2f}")
        print(f"  계산된 포지션 크기: {quantity}주")
        print(f"  거래 금액: ${price * quantity:.2f}")

def test_full_workflow():
    """전체 워크플로우 테스트"""
    print("\n=== 전체 워크플로우 테스트 ===")
    
    fetcher = DataFetcher()
    signal_gen = SignalGenerator()
    trader = Trader(initial_capital=INITIAL_CAPITAL_MIN)
    
    # 첫 번째 원본 주식 사용
    if TARGET_SYMBOLS:
        test_item = TARGET_SYMBOLS[0]
        symbol = test_item["ORIGINAL"]  # 원본 주식 코드
    else:
        symbol = "TSLA"  # 기본값
    
    # 1. 데이터 수집
    print(f"\n1. {symbol} 데이터 수집 중...")
    data = fetcher.get_intraday_data(symbol, interval="5m")
    if data is None:
        print("  데이터 수집 실패")
        return
    
    current_price = fetcher.get_realtime_price(symbol)
    if current_price is None:
        print("  가격 조회 실패")
        return
    
    print(f"  현재가: ${current_price:.2f}")
    
    # 2. 신호 생성
    print(f"\n2. 매매 신호 생성 중...")
    signal_data = signal_gen.generate_signal(data)
    print(f"  신호: {signal_data['signal'].value}")
    print(f"  신뢰도: {signal_data['confidence']:.2f}")
    
    # 3. 거래 실행 (DRY RUN)
    print(f"\n3. 거래 실행 (DRY RUN)...")
    if signal_data['signal'] == SignalType.BUY and signal_data['confidence'] > 0.5:
        position = trader.open_long_position(symbol, current_price)
        if position:
            print(f"  롱 포지션 오픈 성공")
            print(f"  진입가: ${position.entry_price:.2f}")
            print(f"  수량: {position.quantity}")
            
            # 포지션 모니터링 시뮬레이션
            time.sleep(2)
            new_price = fetcher.get_realtime_price(symbol)
            if new_price:
                trader.position_manager.update_position_price(symbol, new_price)
                pnl = position.get_pnl_pct()
                print(f"  현재 손익: {pnl:.2f}%")
    
    elif signal_data['signal'] == SignalType.SELL and signal_data['confidence'] > 0.5:
        position = trader.open_short_position(symbol, current_price)
        if position:
            print(f"  숏 포지션 오픈 성공")
            print(f"  진입가: ${position.entry_price:.2f}")
            print(f"  수량: {position.quantity}")

def main():
    """테스트 메인 함수"""
    print("=" * 50)
    print("거래 봇 테스트 시작")
    print("=" * 50)
    
    # 개별 테스트
    test_data_fetcher()
    test_indicators()
    test_signal_generator()
    test_trader()
    
    # 전체 워크플로우 테스트
    test_full_workflow()
    
    print("\n" + "=" * 50)
    print("테스트 완료")
    print("=" * 50)

if __name__ == "__main__":
    main()

