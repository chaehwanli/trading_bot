from config import settings
from trading.brokers.kis import KisBroker
from trading.brokers.kiwoom import KiwoomBroker
from trading.brokers.base import BaseBroker
from utils.logger import logger

def get_broker() -> BaseBroker:
    """설정에 따라 적절한 브로커 인스턴스 반환"""
    # 설정값 동적 로드
    broker_type = settings.BROKER_TYPE.upper()
    is_paper_trading = settings.PAPER_TRADING
    
    if broker_type == "KIWOOM":
        logger.info(f"브로커 선택: KIWOOM (PaperTrading: {is_paper_trading})")
        return KiwoomBroker(is_paper_trading=is_paper_trading)
        
    elif broker_type == "KIS":
        logger.info(f"브로커 선택: KIS (PaperTrading: {is_paper_trading})")
        return KisBroker(is_paper_trading=is_paper_trading)
        
    else:
        logger.warning(f"알 수 없는 브로커 타입 '{broker_type}'. 기본값 KIS 사용.")
        return KisBroker(is_paper_trading=is_paper_trading)
