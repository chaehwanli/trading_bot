import requests
import json
import time
import os
import sys
from typing import Optional, Dict
from datetime import datetime

# 프로젝트 루트 경로 추가
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)

from config.settings import (
    KIWOOM_SERVER_URL, KIWOOM_ACCOUNT_NO
)
from utils.logger import logger
from trading.brokers.base import BaseBroker

class KiwoomBroker(BaseBroker):
    """
    Kiwoom 증권 OpenAPI 래퍼 클래스 (Relay Server 연동)
    Windows OCX를 직접 호출할 수 없는 Linux 환경을 가정하여,
    Windows에서 실행 중인 Relay Server로 HTTP 요청을 보냄.
    """
    
    def __init__(self, is_paper_trading=False):
        # 키움은 모의투자와 실전투자 접속을 로그인 화면에서 구분함.
        # Relay Server가 이미 로그인된 상태라고 가정.
        self.server_url = KIWOOM_SERVER_URL
        self.account_no = KIWOOM_ACCOUNT_NO
        self.is_paper_trading = is_paper_trading
        
        if not self.server_url:
            logger.warning("KIWOOM_SERVER_URL이 설정되지 않았습니다. 키움 브로커가 정상 동작하지 않을 수 있습니다.")

        logger.info(f"Kiwoom Broker Initialized (Server: {self.server_url})")

    def ensure_valid_token(self):
        """키움은 별도 토큰 관리가 필요없거나 Relay Server가 관리함"""
        # 필요하다면 Relay Server에 핑을 보내 연결 확인
        try:
            res = requests.get(f"{self.server_url}/ping", timeout=5)
            if res.status_code == 200:
                return True
        except Exception as e:
            logger.error(f"Kiwoom Relay Server 접속 실패: {e}")
        return False

    def get_current_price(self, symbol: str) -> Optional[float]:
        """현재가 조회"""
        url = f"{self.server_url}/price"
        params = {"code": symbol}
        
        try:
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            # Relay Server 응답 구조에 따라 다름. 예: {"code": "005930", "price": 70000}
            return float(data.get('price', 0))
        except Exception as e:
            logger.error(f"Kiwoom 시세 조회 실패 ({symbol}): {e}")
            return None

    def get_balance(self) -> float:
        """예수금 조회"""
        url = f"{self.server_url}/balance"
        params = {"account": self.account_no}
        
        try:
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            # 예: {"deposit": 1000000}
            return float(data.get('deposit', 0))
        except Exception as e:
            logger.error(f"Kiwoom 잔고 조회 실패: {e}")
            return 0.0

    def get_minute_price(self, symbol: str, interval_min: int = 60):
        """분봉 조회"""
        url = f"{self.server_url}/chart/minute"
        params = {
            "code": symbol, 
            "tick": interval_min
        }
        
        try:
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            # 예: [{"time": "20240101120000", "open": ..., "close": ...}, ...]
            return data
        except Exception as e:
            logger.error(f"Kiwoom 분봉 조회 실패 ({symbol}): {e}")
            return None

    def place_order(self, symbol: str, side: str, qty: float, price: float = 0, order_type: str = "00") -> Optional[Dict]:
        """주문 전송"""
        url = f"{self.server_url}/order"
        
        # 키움 주문 유형 (1:신규매수, 2:신규매도)
        order_type_int = 1 if side == "BUY" else 2
        
        # 호가 구분 (00:지정가, 03:시장가)
        hoga_gubun = "00" if order_type == "00" else "03"
        
        payload = {
            "account": self.account_no,
            "order_type": order_type_int, 
            "code": symbol,
            "qty": int(qty),
            "price": int(price),
            "hoga": hoga_gubun
        }
        
        try:
            res = requests.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            # 예: {"order_no": "12345", "msg": "주문전송완료"}
            logger.info(f"Kiwoom 주문 전송 성공: {data}")
            return data
        except Exception as e:
            logger.error(f"Kiwoom 주문 전송 실패: {e}")
            return None
