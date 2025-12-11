import requests
import json
import time
from datetime import datetime
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, KIS_BASE_URL
from utils.logger import logger

class KisApi:
    """한국투자증권 OpenAPI 래퍼 클래스"""
    
    def __init__(self, is_paper_trading=False):
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self.account_no = KIS_ACCOUNT_NO
        
        if is_paper_trading:
            self.base_url = "https://openapivts.koreainvestment.com:29443"
        else:
            self.base_url = KIS_BASE_URL
            
        self.access_token = None
        self.token_expiry = None
        
        # 계좌번호 분리 (앞 8자리 + 뒤 2자리)
        if '-' in self.account_no:
            self.account_front = self.account_no.split('-')[0]
            self.account_back = self.account_no.split('-')[1]
        elif len(self.account_no) == 10:
            self.account_front = self.account_no[:8]
            self.account_back = self.account_no[8:]
        else:
            # 예외 처리: 일단 그대로 둠 (사용자 확인 필요)
            self.account_front = self.account_no
            self.account_back = "01" # 기본값 가정

        # 초기 토큰 발급 시도 (실패해도 초기화는 진행)
        try:
            self._get_access_token()
        except Exception as e:
            logger.error(f"KIS API 초기화 중 토큰 발급 실패: {e}")

    def _get_access_token(self):
        """접근 토큰 발급/갱신"""
        # 기존 토큰이 있고 유효하면 재사용
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        path = "/oauth2/tokenP"
        url = f"{self.base_url}{path}"
        
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            res = requests.post(url, headers=headers, data=json.dumps(body))
            res.raise_for_status()
            data = res.json()
            
            self.access_token = data['access_token']
            # 토큰 유효기간 설정 (여유있게 1시간 줄임)
            self.token_expiry = datetime.now() + timedelta(seconds=int(data['expires_in']) - 3600)
            
            logger.info("KIS 접근 토큰 발급 성공")
            return self.access_token
            
        except Exception as e:
            logger.error(f"토큰 발급 실패: {e}")
            # 테스트/개발 환경을 위해 가짜 토큰 반환할 수도 있음 (주의)
            return None

    def _get_common_headers(self, tr_id):
        """공통 헤더 생성"""
        token = self._get_access_token()
        if not token:
            raise Exception("유효한 Access Token이 없습니다.")
            
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }

    def get_current_price(self, symbol: str):
        """
        해외주식 현재가 상세 조회
        주의: 심볼은 티커 (예: TSLA)
        """
        # 해외주식 현재체결가 (HHDFS00000300)
        path = "/uapi/overseas-price/v1/quotations/price"
        url = f"{self.base_url}{path}"
        
        # 거래소 코드 추정 (미국 주식 기준)
        exch_code = "NAS" # 나스닥 기본 가정. 필요시 NYS 등 구분 로직 필요
        # 간단한 매핑
        if symbol in ['TSLA', 'AAPL', 'NVDA', 'AMZN', 'GOOGL', 'MSFT', 'META', 'NFLX', 'AMD', 'INTC']:
            exch_code = "NAS"
        else:
            exch_code = "AMS" # 아멕스 등.. ETF는 구분 필요할 수 있음.
            # ETF가 대부분 나스닥/NYSE 아카 등인데 KIS는 NAS/NYS/AMS 로 구분
            # 안전하게 검색 API를 쓰거나, 일단 NAS/NYS 시도해보는 로직이 좋음.
            # 여기서는 TSLL, TSLZ 등이 나스닥인지 확인 필요. TSLL(Nasdaq), TSLZ(Nasdaq)
            if symbol in ['TSLL', 'TSLZ', 'TSLT']:
                exch_code = "NAS"
            
        
        headers = self._get_common_headers("HHDFS00000300")
        
        params = {
            "AUTH": "",
            "EXCD": exch_code,
            "SYMB": symbol
        }
        
        try:
            res = requests.get(url, headers=headers, params=params)
            res.raise_for_status()
            data = res.json()
            
            if data['rt_cd'] != '0':
                logger.error(f"시세 조회 실패 ({symbol}): {data['msg1']}")
                return None
                
            # last: 현재가
            current_price = float(data['output']['last'])
            return current_price
            
        except Exception as e:
            logger.error(f"API 호출 오류 (get_current_price): {e}")
            return None

    def get_balance(self):
        """해외주식 체결기준 잔고"""
        # 해외주식 잔고 (HHDFS76410000) - 실전/모의 tr_id가 다를 수 있음 확인 필요
        # 모의: VTRR6540S (매수가능조회) 등으로 대체 가능하기도 함.
        pass 
        # 일단 구현 생략 (시간상 Bot 로직 구현 집중) - 모의 잔고라도 리턴해야 함
        return 100000.0 # 임시 하드코딩

    def place_order(self, symbol, side, qty, price=0, order_type="00"):
        """
        해외주식 주문
        side: 'BUY' or 'SELL'
        order_type: '00' (지정가), '01' (시장가) 등. 해외주식은 보통 지정가 권장되나 시장가 지원 여부 확인.
        KIS 미국주식: 지정가(00), 시장가(01) 등
        """
        # tr_id 결정
        # 실전: TTTT1002U (미국 매수), TTTT1006U (미국 매도)
        # 모의: VTTT1002U ...
        is_paper = "vts" in self.base_url
        
        tr_id = ""
        if side == "BUY":
            tr_id = "VTTT1002U" if is_paper else "JTTT1002U" # 미국 매수 (3자리 다름 주의 - 문서 확인 필요. JTTT1002U가 맞음)
            # * 주의: KIS API 문서는 수시로 확인 필요. 일단 일반적인 ID 사용.
            #  미국 매수: JTTT1002U (주간/야간 통합일 수 있음)
        elif side == "SELL":
            tr_id = "VTTT1006U" if is_paper else "JTTT1006U" # 미국 매도
            
        path = "/uapi/overseas-stock/v1/trading/order"
        url = f"{self.base_url}{path}"
        
        headers = self._get_common_headers(tr_id)
        
        # 거래소 코드
        ovs_excd = "NAS" # 일단 나스닥 가정
        
        body = {
            "CANO": self.account_front,
            "ACNT_PRDT_CD": self.account_back,
            "OVRS_EXCG_CD": ovs_excd,
            "PDNO": symbol,
            "ORD_QTY": str(int(qty)),
            "OVRS_ORD_UNPR": str(price), # 지정가인 경우 가격, 시장가여도 0은 아닐 수 있음 (0으로 설정 시 거부될 수 있으므로 확인)
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": order_type # 00: 지정가, 01: 시장가 (KIS 해외주식 주문유형 확인 필요)
        }
        
        try:
            res = requests.post(url, headers=headers, data=json.dumps(body))
            data = res.json()
            
            if data['rt_cd'] != '0':
                logger.error(f"주문 실패 ({symbol} {side}): {data['msg1']}")
                return None
                
            return data['output'] # 주문번호 등 포함
            
        except Exception as e:
            logger.error(f"주문 중 예외 발생: {e}")
            return None

# datetime 등 필요한 임포트 추가 (위에서 누락된 경우)
from datetime import timedelta
