import sys
import os
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading.kis_api import KisApi
from utils.logger import logger

def test_balance():
    # 모의투자 모드로 설정
    kis = KisApi(is_paper_trading=True)
    
    logger.info("모의투자 계좌 잔고 조회 테스트 시작...")
    balance = kis.get_overseas_stock_balance()
    
    if balance:
        logger.info("=== 보유 종목 (holdings) ===")
        for item in balance['holdings']:
            logger.info(f"Symbol: {item.get('ovrs_pdno')}, Qty: {item.get('ovrs_ccl_qty')}, Price: {item.get('papr_avg_unit_pric')}")
        
        logger.info("=== 계좌 자산 (assets) ===")
        print(balance['assets'])
    else:
        logger.error("잔고 조회 실패")

if __name__ == "__main__":
    test_balance()
