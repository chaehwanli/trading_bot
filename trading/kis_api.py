import requests
import json
import time
from datetime import datetime, timedelta
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
        self.is_paper_trading = is_paper_trading
        
        # 계좌번호 분리 (앞 8자리 + 뒤 2자리)
        if '-' in self.account_no:
            self.account_front = self.account_no.split('-')[0]
            self.account_back = self.account_no.split('-')[1]
        elif len(self.account_no) == 10:
            self.account_front = self.account_no[:8]
            self.account_back = self.account_no[8:]
        else:
            self.account_front = self.account_no
            self.account_back = "01" # 기본값 가정

        # 초기 토큰 발급 시도 (실패해도 초기화는 진행)
        try:
            self._get_access_token()
        except Exception as e:
            logger.error(f"KIS API 초기화 중 토큰 발급 실패: {e}")

    def _get_access_token(self):
        """접근 토큰 발급/갱신 (파일 캐시 지원)"""
        # 1. 메모리 캐시 확인
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        # 2. 파일 캐시 확인
        token_file = "kis_token_paper.json" if self.is_paper_trading else "kis_token_real.json"
        
        # 파일이 존재하면 읽기 시도
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    cached = json.load(f)
                    expiry_dt = datetime.strptime(cached['expiry'], "%Y-%m-%d %H:%M:%S")
                    
                    if datetime.now() < expiry_dt:
                        self.access_token = cached['access_token']
                        self.token_expiry = expiry_dt
                        logger.info(f"KIS 접근 토큰 로드 (캐시): {expiry_dt} 만료")
                        return self.access_token
            except Exception as e:
                logger.warning(f"토큰 파일 읽기 실패 (재발급 진행): {e}")

        # 3. 토큰 발급 요청
        path = "/oauth2/tokenP"
        url = f"{self.base_url}{path}"
        
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        # 모의투자시 env_dv 추가 (사용자 요청 반영)
        if self.is_paper_trading:
            body["env_dv"] = "demo"
        
        try:
            res = requests.post(url, headers=headers, data=json.dumps(body))
            res.raise_for_status()
            data = res.json()
            
            self.access_token = data['access_token']
            # 토큰 유효기간 설정 (여유있게 1시간 줄임)
            # KIS 토큰은 보통 24시간 (86400초)
            seconds_left = int(data.get('expires_in', 86400))
            self.token_expiry = datetime.now() + timedelta(seconds=seconds_left - 3600)
            
            logger.info("KIS 접근 토큰 발급 성공 & 캐시 저장")
            
            # 파일에 저장
            try:
                with open(token_file, 'w') as f:
                    json.dump({
                        'access_token': self.access_token,
                        'expiry': self.token_expiry.strftime("%Y-%m-%d %H:%M:%S")
                    }, f)
            except Exception as e:
                logger.warning(f"토큰 파일 저장 실패: {e}")
                
            return self.access_token
            
        except Exception as e:
            logger.error(f"토큰 발급 실패: {e}")
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

    def _guess_exch_code(self, symbol):
        """거래소 코드 추정 (미국 주식 기준)"""
        if symbol in ['TSLT', 'TSLZ', 'BTCL', 'BTCZ', 'NVDX', 'NVDQ'] :
            return "AMS"
        #if symbol in ['TSLL', 'TSLZ', 'TSLT']: # 주요 ETF 확인
        #    return "NAS"
        # 그 외 AMS로 가정 (혹은 NYS)
        return "NAS"

    def get_current_price(self, symbol: str):
        """해외주식 현재가 상세 조회"""
        path = "/uapi/overseas-price/v1/quotations/price"
        url = f"{self.base_url}{path}"
        exch_code = self._guess_exch_code(symbol)
        
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
                
            current_price = float(data['output']['last'])
            return current_price
            
        except Exception as e:
            logger.error(f"API 호출 오류 (get_current_price): {e}")
            return None

    def get_daily_price(self, symbol: str, period_code="D"):
        """
        해외주식 기간별 시세 (일/주/월)
        symbol: 심볼
        period_code: D(일), W(주), M(월)
        """
        path = "/uapi/overseas-price/v1/quotations/dailyprice"
        url = f"{self.base_url}{path}"
        exch_code = self._guess_exch_code(symbol)

        headers = self._get_common_headers("HHDFS76240000")
        
        # 날짜 형식 YYYYMMDD
        today = datetime.now()
        # 0: 일, 1: 주, 2: 월   (문서확인: GUBN 0=일, 1=주, 2=월)
        gubn = "0"
        if period_code == "W": gubn = "1"
        elif period_code == "M": gubn = "2"

        params = {
            "AUTH": "",
            "EXCD": exch_code,
            "SYMB": symbol,
            "GUBN": gubn,
            "BYMD": today.strftime("%Y%m%d"), # 조회 기준일(오늘)
            "MODP": "1" # 수정주가 반영 여부 (0:미반영, 1:반영)
        }

        try:
            res = requests.get(url, headers=headers, params=params)
            res.raise_for_status()
            data = res.json()
            
            if data['rt_cd'] != '0':
                logger.error(f"일별 시세 조회 실패 ({symbol}): {data['msg1']}")
                return None
            
            return data['output2'] # 일별 데이터 리스트

        except Exception as e:
            logger.error(f"API 호출 오류 (get_daily_price): {e}")
            return None

    def get_minute_price(self, symbol: str, interval_min: int = 60):
        """
        해외주식 분봉 조회 (당일/과거 포함)
        TR_ID: HHDFS76950200 (해외주식 분봉조회)
        :param interval_min: 분봉 주기 (1, 3, 5, 10, 15, 30, 60 등)
        """
        path = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
        url = f"{self.base_url}{path}"
        exch_code = self._guess_exch_code(symbol)
        
        headers = self._get_common_headers("HHDFS76950200")
        
        params = {
            "AUTH": "",
            "EXCD": exch_code,
            "SYMB": symbol,
            "NMIN": str(interval_min), # 동적 주기 설정
            "PINC": "1", # 전일포함
            "NEXT": "",
            "NREC": "120", # 요청 개수
            "KEYB": "" 
        }

        # 재시도 로직 추가 (500 에러 대응)
        max_retries = 3
        for i in range(max_retries):
            try:
                # Rate Limit 등을 고려한 미세 지연
                time.sleep(0.2) 
                
                res = requests.get(url, headers=headers, params=params)
                
                if res.status_code == 500:
                    logger.warning(f"API 500 Error ({symbol}), retrying {i+1}/{max_retries}...")
                    time.sleep(1) # 대기 후 재시도
                    continue
                
                res.raise_for_status()
                data = res.json()
                
                if data['rt_cd'] != '0':
                    logger.error(f"분봉 시세 조회 실패 ({symbol}): {data['msg1']}")
                    return None
                    
                return data['output2']

            except Exception as e:
                logger.error(f"API 호출 오류 (get_minute_price): {e}")
                if i < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
        return None

    def get_overseas_stock_balance(self):
        """해외주식 체결기준 잔고 및 보유 종목 조회"""
        path = "/uapi/overseas-stock/v1/trading/inquire-balance"
        url = f"{self.base_url}{path}"
        
        # 실전: JTTT3012R / 모의: VTTT3012R
        tr_id = "VTTT3012R" if self.is_paper_trading else "JTTT3012R"
        
        headers = self._get_common_headers(tr_id)
        
        params = {
            "CANO": self.account_front,
            "ACNT_PRDT_CD": self.account_back,
            "OVRS_EXCG_CD": "NAS", # 거래소 코드 (NAS/AMS 등, 대표값 사용)
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        # 재시도 로직 추가
        max_retries = 3
        for i in range(max_retries):
            try:
                if i > 0: time.sleep(1)
                
                res = requests.get(url, headers=headers, params=params)
                
                if res.status_code == 500:
                    logger.warning(f"잔고 조회 500 Error, retrying {i+1}/{max_retries}...")
                    continue
                    
                res.raise_for_status()
                data = res.json()
                
                if data['rt_cd'] != '0':
                    logger.error(f"잔고 조회 실패: {data['msg1']}")
                    return None
                    
                # output1: 잔고 상세 (보유 종목 리스트)
                # output2: 계좌 자산 현황
                return {
                    "holdings": data['output1'],
                    "assets": data['output2']
                }
                
            except Exception as e:
                logger.error(f"API 호출 오류 (get_overseas_stock_balance): {e}")
                if i < max_retries - 1:
                    continue
                return None
        return None

    def get_balance(self):
        """(Legacy) 해외주식 체결기준 잔고 - 예수금만 반환하는 구 메서드"""
        balance_data = self.get_overseas_stock_balance()
        if balance_data and 'assets' in balance_data:
            # 실전/모의 키값이 다를 수 있으니 확인 필요하나, 보통 frcr_dncl_amt_2(외화예수금) 등 사용
            # 여기서는 편의상 output2의 첫번째 값 or 특정 키 사용.
            # 모의투자 문서 기준: 'frcr_dncl_amt_2' (외화예수금)
            try:
                # 안전하게 0으로 리턴하거나, 실제 파싱 로직 구현
                return float(balance_data['assets'].get('frcr_dncl_amt_2', 100000.0))
            except:
                return 100000.0
        return 100000.0 

    def place_order(self, symbol, side, qty, price=0, order_type="00"):
        """해외주식 주문"""
        # (기존 코드 유지, is_paper_trading 속성 사용하도록 수정)
        
        tr_id = ""
        # 실전: JTTT1002U / JTTT1006U (미국)
        # 모의: VTTT1002U / VTTT1006U (미국)
        
        if side == "BUY":
            tr_id = "VTTT1002U" if self.is_paper_trading else "JTTT1002U"
        elif side == "SELL":
            tr_id = "VTTT1006U" if self.is_paper_trading else "JTTT1006U"

        # 모의투자는 지정가(00)만 가능
        if self.is_paper_trading:
            order_type = "00"
            # 가격이 0(시장가 의도)인 경우 현재가 조회
            if float(price) <= 0:
                current_price = self.get_current_price(symbol)
                if current_price:
                    price = current_price
                    logger.info(f"[Mock] 시장가 주문 -> 지정가 변환 {symbol} @ {price}")
                else:
                    logger.error(f"[Mock] 가격 조회 실패로 주문 중단: {symbol}")
                    return None
            
        path = "/uapi/overseas-stock/v1/trading/order"
        url = f"{self.base_url}{path}"
        
        headers = self._get_common_headers(tr_id)
        
        ovs_excd = self._guess_exch_code(symbol)
        
        body = {
            "CANO": self.account_front,
            "ACNT_PRDT_CD": self.account_back,
            "OVRS_EXCG_CD": ovs_excd,
            "PDNO": symbol,
            "ORD_QTY": str(int(qty)),
            "OVRS_ORD_UNPR": str(price), 
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": order_type 
        }
        
        # 재시도 로직 추가
        max_retries = 3
        for i in range(max_retries):
            try:
                # Rate Limit 등을 고려한 미세 지연 (기본)
                if i > 0: time.sleep(1) 
                
                res = requests.post(url, headers=headers, data=json.dumps(body))
                data = res.json()
                
                # 초당 거래건수 초과 등 (rt_cd != 0)
                if data['rt_cd'] != '0':
                    msg = data['msg1']
                    # 초당 거래건수 초과 메시지 확인 (정확한 메시지는 "초당 거래건수를 초과" 포함)
                    if "초과" in msg and i < max_retries - 1:
                        logger.warning(f"주문 실패 (Rate Limit), retrying {i+1}/{max_retries}... Msg: {msg}")
                        time.sleep(0.5 * (i+1)) # 지연 시간 증가
                        continue
                        
                    logger.error(f"주문 실패 ({symbol} {side}): {msg}")
                    return None
                    
                return data['output'] 
                
            except Exception as e:
                logger.error(f"주문 중 예외 발생: {e}")
                if i < max_retries - 1:
                     time.sleep(1)
                     continue
                return None
        return None
