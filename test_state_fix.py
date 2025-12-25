import sys
import os
import json
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tesla_reversal_trading_bot import TeslaReversalTradingBot
from utils.logger import logger

def test_restoration():
    # 1. 가짜 상태 파일 생성
    mock_state = {
        "current_position": "SHORT",
        "current_etf_symbol": "TSLS",
        "entry_price": 4.72,
        "entry_time": datetime.now().isoformat(),
        "entry_quantity": 241.53,
        "capital": 59.98
    }
    
    with open("bot_state.json", "w", encoding="utf-8") as f:
        json.dump(mock_state, f, indent=4)
        
    logger.info("테스트용 bot_state.json 생성 완료")
    
    # 2. 봇 초기화 (실제 API 호출을 최소화하기 위해 객체만 생성)
    # KisApi 토큰 발급 등은 발생할 수 있음
    try:
        bot = TeslaReversalTradingBot(is_paper_trading=True)
        
        # 3. 전략 상태 확인
        status = bot.strategy.get_strategy_status()
        logger.info(f"복구된 상태: {status['current_position']} ({status['current_etf']}), Capital: {status['capital']}")
        
        if status['current_position'] == "SHORT" and status['current_etf'] == "TSLS":
            logger.info("✅ 포지션 복구 성공")
        else:
            logger.error("❌ 포지션 복구 실패")
            
        # 4. 동기화 로직 테스트 (KIS에 종목이 없으므로 경고가 떠야 함)
        logger.info("계좌 동기화 로직 실행 (경고가 발생해야 정상)...")
        bot.sync_internal_state_with_account()
        
        # 다시 상태 로드해서 지워졌는지 확인 (지워지면 안됨)
        with open("bot_state.json", "r", encoding="utf-8") as f:
            final_state = json.load(f)
            
        if final_state.get('current_position') == "SHORT":
            logger.info("✅ 비파괴적 동기화 성공 (정보가 유지됨)")
        else:
            logger.error("❌ 오류: 정보가 삭제됨")

    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    test_restoration()
