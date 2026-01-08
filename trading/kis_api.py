import requests
import json
import time
from datetime import datetime, timedelta
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    KIS_REAL_APP_KEY, KIS_REAL_APP_SECRET, KIS_REAL_ACCOUNT_NO, KIS_REAL_BASE_URL,
    KIS_PAPER_APP_KEY, KIS_PAPER_APP_SECRET, KIS_PAPER_ACCOUNT_NO, KIS_PAPER_BASE_URL
)
from utils.logger import logger

class KisApi:
    """한국투자증권 OpenAPI 래퍼 클래스"""
    
    def __init__(self, is_paper_trading=False):
        if is_paper_trading:
            self.app_key = KIS_PAPER_APP_KEY
            self.app_secret = KIS_PAPER_APP_SECRET
            self.account_no = KIS_PAPER_ACCOUNT_NO
            self.base_url = KIS_PAPER_BASE_URL
        else:
            self.app_key = KIS_REAL_APP_KEY
            self.app_secret = KIS_REAL_APP_SECRET
            self.account_no = KIS_REAL_ACCOUNT_NO
            self.base_url = KIS_REAL_BASE_URL
            
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
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_name = "kis_token_paper.json" if self.is_paper_trading else "kis_token_real.json"
        token_file = os.path.join(root_dir, file_name)
        
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
            # 토큰 유효기간 설정 (여유있게 3시간 줄임)
            # KIS 토큰은 보통 24시간 (86400초)
            seconds_left = int(data.get('expires_in', 86400))
            self.token_expiry = datetime.now() + timedelta(seconds=seconds_left - 10800)
            
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
            
    def ensure_valid_token(self):
        """토큰이 유효한지 확인하고 필요시 갱신 (만료 3시간 전)"""
        if not self.access_token or not self.token_expiry or datetime.now() >= self.token_expiry:
            logger.info("토큰 만료 또는 없음 - 발급 진행")
            return self._get_access_token()
        
        # 만료 3시간 이내인지 확인 (이미 _get_access_token에서 3시간을 뺐으므로 현재 시간이 token_expiry를 지났다면 갱신 필요)
        return self.access_token

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
        """거래소 코드 추정"""
        # 한국 주식 (6자리 숫자)
        if symbol.isdigit() and len(symbol) == 6:
            return "KRX"
            
        if symbol in ['TSLT', 'TSLZ', 'BTCL', 'BTCZ', 'NVDX', 'NVDQ'] :
            return "AMS"
        return "NAS"

    def get_current_price(self, symbol: str):
        """현재가 상세 조회 (국내/해외 분기)"""
        exch_code = self._guess_exch_code(symbol)
        
        if exch_code == "KRX":
            # 국내 주식 현재가 상세 조회
            path = "/uapi/domestic-stock/v1/quotations/inquire-price"
            url = f"{self.base_url}{path}"
            headers = self._get_common_headers("FHKST01010100")
            params = {
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": symbol
            }
        else:
            # 해외 주식 현재가 상세 조회
            path = "/uapi/overseas-price/v1/quotations/price"
            url = f"{self.base_url}{path}"
            headers = self._get_common_headers("HHDFS00000300")
            params = {
                "AUTH": "",
                "EXCD": exch_code,
                "SYMB": symbol
            }
    
        logger.debug(f"[API] get_current_price Request - URL: {url}, Params: {params}")

        # 재시도 로직 추가 (500 에러 대응)
        max_retries = 3
        for i in range(max_retries):
            try:
                # API 호출 간격 조절
                if i > 0: time.sleep(1)
                
                res = requests.get(url, headers=headers, params=params)
                
                if res.status_code == 500:
                    logger.warning(f"시세 조회 500 Error ({symbol}), retrying {i+1}/{max_retries}...")
                    continue
                
                res.raise_for_status()
                data = res.json()
                
                if data['rt_cd'] != '0':
                    logger.error(f"시세 조회 실패 ({symbol}): {data['msg1']}")
                    return None
                    
                if exch_code == "KRX":
                    current_price = float(data['output']['stck_prpr'])
                else:
                    current_price = float(data['output']['last'])
                return current_price
                
            except Exception as e:
                logger.error(f"API 호출 오류 (get_current_price): {e}")
                if i < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
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
        
        # 실전: TTTT3012R / 모의: VTTT3012R
        tr_id = "VTTT3012R" if self.is_paper_trading else "TTTT3012R"
        
        headers = self._get_common_headers(tr_id)
        
        params = {
            "CANO": self.account_front,
            "ACNT_PRDT_CD": self.account_back,
            "OVRS_EXCG_CD": "NAS", # 거래소 코드 (NAS/AMS 등, 대표값 사용)
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        logger.debug(f"[API] get_overseas_stock_balance Request - tr_id: {tr_id}, URL: {url}, Params: {params}")
        
        # 재시도 로직 추가
        max_retries = 3
        for i in range(max_retries):
            try:
                if i > 0: time.sleep(1)
                
                res = requests.get(url, headers=headers, params=params)
                
                if res.status_code == 500:
                    logger.warning(f"잔고 조회 500 Error, retrying {i+1}/{max_retries}...")
                    logger.debug(f"[API] get_overseas_stock_balance Response - Data: {res.json()}")
                    continue
                    
                res.raise_for_status()
                data = res.json()
                
                if data['rt_cd'] != '0':
                    logger.error(f"잔고 조회 실패: {data['msg1']}")
                    return None
                    
                # output1: 잔고 상세 (보유 종목 리스트)
                # output2: 계좌 자산 현황
                logger.debug(f"[API] get_overseas_stock_balance Response - Data: {data}")

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

    def get_overseas_trades(self):
        """체결 내역 확인 (즉시 반영)"""
        path = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
        url = f"{self.base_url}{path}"
        
        # 실전: TTTT3012R / 모의: VTTT3012R
        tr_id = "VTTS3035R" if self.is_paper_trading else "TTTS3035R"
        
        headers = self._get_common_headers(tr_id)
        
        params = {
            "CANO": self.account_front,
            "ACNT_PRDT_CD": self.account_back,
            "OVRS_EXCG_CD": "NAS", # 거래소 코드 (NAS/AMS 등, 대표값 사용)
            "TR_CRCY_CD": "USD",
            "PDNO": "TSLS",
            "ORD_DT": "20260108",
            "ORD_STRT_DT": "20260101",  # ✅ 조회 시작일자
            "ORD_END_DT": "20260108",     # ✅ 조회 종료일자
            "INQR_DVSN": "01",          # ✅ 기간 조회 모드
            "SLL_BUY_DVSN": "00",
            "CCLD_NCCS_DVSN": "00",
            "SORT_SQN": "DS", 
            "ORD_GNO_BRNO": "000", 
            "ODNO": "0000000000",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        logger.debug(f"[API] get_overseas_trades Request - tr_id: {tr_id}, URL: {url}, Params: {params}")
        
        # 재시도 로직 추가
        max_retries = 3
        for i in range(max_retries):
            try:
                if i > 0: time.sleep(1)
                
                res = requests.get(url, headers=headers, params=params)
                
                if res.status_code == 500:
                    logger.warning(f"체결 내역 확인 500 Error, retrying {i+1}/{max_retries}...")
                    continue
                    
                res.raise_for_status()
                data = res.json()
                
                if data['rt_cd'] != '0':
                    logger.error(f"체결 내역 확인 실패: {data['msg1']}")
                    return None
                    
                #{
                #    "rt_cd": "0",
                #    "msg_cd": "00000",
                #    "msg1": "정상처리되었습니다.",
                #    "output": [
                #        {
                #            "ovrs_pdno": "TSLS",
                #            "ord_dvsn_name": "매수",
                #            "ovrs_ccld_qty": "1",
                #            "frcr_ccld_amt": "5.33"
                #        }
                #    ]
                #}
                logger.debug(f"[API] get_overseas_trades Response - Data: {data}")

                return {
                    "output": data.get("output", [])
                }
                
            except Exception as e:
                logger.error(f"API 호출 오류 (get_overseas_trades): {e}")
                if i < max_retries - 1:
                    continue
                return None
        return None

    def get_balance(self):
        """해외주식 USD 예수금 조회 (get_overseas_stock_balance -> frcr_dncl_amt_2)"""
        # KIS OpenAPI 공식 가이드: frcr_dncl_amt_2 사용
        balance_data = self.get_overseas_stock_balance()
        if balance_data and 'assets' in balance_data:
            assets = balance_data['assets']
            try:
                val = assets.get('frcr_dncl_amt_2')
                if val:
                    return float(val)
            except:
                pass
        return 0.0 

    def place_order(self, symbol, side, qty, price=0, order_type="00"):
        """해외주식 주문"""
        # (기존 코드 유지, is_paper_trading 속성 사용하도록 수정)
        
        tr_id = ""
        # 실전: JTTT1002U / JTTT1006U (미국)
        # 모의: VTTT1002U / VTTT1006U (미국)
        
        if side == "BUY":
            tr_id = "VTTT1002U" if self.is_paper_trading else "TTTT1002U"
        elif side == "SELL":
            tr_id = "VTTT1006U" if self.is_paper_trading else "TTTT1006U"

        ovs_excd = self._guess_exch_code(symbol)
        
        # 주문용 거래소 코드 매핑 (시세조회용 3자리 -> 주문용 4자리)
        # NAS -> NASD, AMS -> AMEX, NYS -> NYSE
        order_exch_map = {
            "NAS": "NASD",
            "AMS": "AMEX",
            "NYS": "NYSE"
        }
        order_exch_code = order_exch_map.get(ovs_excd, ovs_excd)
        
        # 미국 시장(NAS/AMS/NYS 등)은 시장가(01) 주문 시 '주문구분 입력오류'가 발생하는 경우가 많음
        # 따라서 시장가 요청 시 지정가(00) + 현재가(여유가)로 변환하여 전송
        if ovs_excd != "KRX" and order_type == "01":
            logger.info(f"[{order_exch_code}] 시장가 주문을 지정가(여유가)로 변환합니다. (PaperTrading: {self.is_paper_trading})")
            order_type = "00"
            if float(price) <= 0:
                curr_price = self.get_current_price(symbol)
                if curr_price:
                    # 매수는 현재가보다 1호가(1센트) 높게, 매도는 1호가 낮게 설정하여 즉시 체결 유도
                    # (사용자 요청 반영: 호가단위 1센트 기준 1호가 버퍼 적용)
                    if side == "BUY":
                        price = round(curr_price + 0.01, 2)
                    else:
                        price = round(curr_price - 0.01, 2)
                    logger.info(f"[{order_exch_code}] 시장가 대체 지정가 (1호가 버퍼): {curr_price} -> {price}")
                else:
                    logger.error(f"[{order_exch_code}] 현재가 조회 실패로 주문을 진행할 수 없습니다.")
                    return None
        
        if ovs_excd == "KRX":
            # 국내 주식 현금 주문
            path = "/uapi/domestic-stock/v1/trading/order-cash"
            url = f"{self.base_url}{path}"
            
            # 실전: TTTC0802U(매수), TTTC0801U(매도)
            # 모의: VTTC0802U(매수), VTTC0801U(매도)
            if side == "BUY":
                tr_id = "VTTC0802U" if self.is_paper_trading else "TTTC0802U"
            else:
                tr_id = "VTTC0801U" if self.is_paper_trading else "TTTC0801U"
                
            headers = self._get_common_headers(tr_id)
            body = {
                "CANO": self.account_front,
                "ACNT_PRDT_CD": self.account_back,
                "PDNO": symbol,
                "ORD_DVSN": "01" if order_type == "01" else "00", # 00: 지정가, 01: 시장가
                "ORD_QTY": str(int(qty)),
                # 국내 주식 호가단위(10원) 반영 (사용자 요청: 10원 단위로 반올림)
                "ORD_UNPR": str(int(round(float(price), -1))) if order_type == "00" else "0"
            }
        else:
            # 해외 주식 주문
            path = "/uapi/overseas-stock/v1/trading/order"
            url = f"{self.base_url}{path}"
            headers = self._get_common_headers(tr_id)
            body = {
                "CANO": self.account_front,
                "ACNT_PRDT_CD": self.account_back,
                "OVRS_EXCG_CD": order_exch_code, # NASD, AMEX 등으로 변경됨
                "PDNO": symbol,
                "ORD_QTY": str(int(qty)),
                "OVRS_ORD_UNPR": str(price), 
                "ORD_SVR_DVSN_CD": "0",
                "ORD_DVSN": order_type 
            }
        
        logger.debug(f"주문 요청 Body: {body}")
        
        # 재시도 로직 추가
        max_retries = 3
        for i in range(max_retries):
            try:
                # Rate Limit 등을 고려한 미세 지연 (기본)
                if i > 0: time.sleep(1) 

                logger.debug(f"[API] place_order Request - URL: {url}, Body: {json.dumps(body)}")
                
                res = requests.post(url, headers=headers, data=json.dumps(body))
                data = res.json()
                
                # 초당 거래건수 초과 등 (rt_cd != 0)
                if data['rt_cd'] != '0':
                    msg = data['msg1']
                    # 초당 거래건수 초과 메시지 확인 (정확한 메시지는 "초당 거래건수를 초과" 포함)
                    if "초당 거래건수" in msg and i < max_retries - 1:
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
