"""
시장 데이터 수집 모듈
- KIS API 전용 (YFinance, DB Cache 제거)
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import logger
from trading.kis_api import KisApi

class DataFetcher:
    """시장 데이터 수집 클래스 (KIS API)"""
    
    def __init__(self, kis_client: Optional[KisApi] = None):
        """
        :param kis_client: 외부에서 주입된 KisApi 인스턴스 (없으면 내부 생성)
        """
        if kis_client:
            self.kis = kis_client
        else:
            # 기본값: 실전 투자 (주의: 모의투자 시 외부 주입 권장)
            self.kis = KisApi(is_paper_trading=False)
    
    def get_realtime_price(self, symbol: str) -> Optional[float]:
        """실시간 가격 조회"""
        return self.kis.get_current_price(symbol)
        #"""실시간 가격 조회 (KIS 우선 -> 실패시 yfinance)"""
        # price = self.kis.get_current_price(symbol)
        # if price:
        #     return price
            
        # try:
        #     import yfinance as yf
        #    logger.info(f"KIS API 가격 조회 실패, yfinance 시도: {symbol}")
        #    ticker = yf.Ticker(symbol)
        #    # data = ticker.history(period="1m") # 느림
        #    # if not data.empty:
        #    #     return float(data['Close'].iloc[-1])
            
        #    # fast_info 사용 권장
        #    if hasattr(ticker, 'fast_info') and 'last_price' in ticker.fast_info:
        #         return float(ticker.fast_info['last_price'])
                 
        #    # Fallback to history if fast_info fails
        #    data = ticker.history(period='1d')
        #    if not data.empty:
        #        return float(data['Close'].iloc[-1])
                
        #except Exception as e:
        #    logger.error(f"yfinance 가격 조회 실패: {e}")
            
        #return None
    
    def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1mo",
        interval: str = "1h"
    ) -> Optional[pd.DataFrame]:
        """
        과거 데이터 조회 (KIS API)
        period: 1d, 1mo 등 (KIS API에서는 일별 개수 or 기간으로 변환 필요)
        interval: 1h, 1d 등
        """
        try:
            logger.info(f"{symbol} KIS API에서 데이터 다운로드 중... (기간: {period})")
            
            data_list = []
            
            # KIS API 로직 매핑
            if interval in ["1d", "1wk", "1mo"]:
                # 일/주/월봉
                p_code = "D"
                if interval == "1wk": p_code = "W"
                elif interval == "1mo": p_code = "M"
                
                raw_data = self.kis.get_daily_price(symbol, p_code)
                if raw_data:
                    # KIS 일별 데이터 필드: rsym(날짜), clos(종가), open(시가), high(고가), low(저가), evol(거래량) 등
                    # API 문서 확인 필요. 보통: kymd(일자), clos, open, high, low, evol(체결량)
                    # output2 리스트
                    for item in raw_data:
                        data_list.append({
                            "datetime": datetime.strptime(item.get("xymd", item.get("kymd", "")), "%Y%m%d"),
                            "open": float(item.get("open", 0)),
                            "high": float(item.get("high", 0)),
                            "low": float(item.get("low", 0)),
                            "close": float(item.get("clos", 0)),
                            "volume": float(item.get("tvol", item.get("evol", 0)))
                        })
                        
            else:
                # 분봉 (1h -> 60분)
                # Interval Parsing
                interval_min = 60 # 기본값
                if interval.endswith("m"):
                    try:
                        interval_min = int(interval[:-1])
                    except:
                        interval_min = 60
                elif interval.endswith("h"):
                    try:
                        interval_min = int(interval[:-1]) * 60
                    except:
                        interval_min = 60
                
                raw_data = self.kis.get_minute_price(symbol, interval_min=interval_min)
                if raw_data:
                    # KIS 분봉 데이터 필드: kymd(일자), khms(시간), open, high, low, last, evol
                    for item in raw_data:
                        dt_str = f"{item['kymd']}{item['khms']}"
                        data_list.append({
                            "datetime": datetime.strptime(dt_str, "%Y%m%d%H%M%S"),
                            "open": float(item.get("open", 0)),
                            "high": float(item.get("high", 0)),
                            "low": float(item.get("low", 0)),
                            "close": float(item.get("last", 0)),
                            "volume": float(item.get("tvol", item.get("evol", 0)))
                        })

            if not data_list:
                logger.warning(f"{symbol}: 데이터 없음 (KIS)")
                return None
            
            # DataFrame 변환
            df = pd.DataFrame(data_list)
            df.set_index("datetime", inplace=True)
            df.sort_index(inplace=True)
            
            # 기간 필터링은 API가 주는대로 받음 (기간 지정이 어려운 경우가 많음)
            
            logger.debug(f"{symbol} 데이터 로드 성공: {len(df)}개")
            return df
            
        except Exception as e:
            logger.error(f"{symbol} 데이터 조회 실패: {e}")
            return None
    
    def get_intraday_data(
        self, 
        symbol: str, 
        interval: str = "5m"
    ) -> Optional[pd.DataFrame]:
        """당일 분봉 데이터 조회"""
        # KIS는 분봉 조회 시 당일/과거 포함해서 줌. 5분봉 등 로직 추가 필요하나
        # 일단 historical_data(분봉)와 유사.
        # 여기서는 'minute' 호출을 활용하되 interval 처리 필요.
        # kis_api.get_minute_price는 현재 60(1시간) 하드코딩 되어 있으므로,
        # 제대로 쓰려면 kis_api를 수정하여 interval 인자를 받게 해야 함.
        # 일단 1시간봉 위주로 돌아간다면 get_historical_data("1h") 사용 권장.
        # (구현 간소화를 위해 get_historical_data 호출)
        return self.get_historical_data(symbol, period="1d", interval=interval)
    
    def get_market_status(self, symbol: str) -> Dict[str, any]:
        """시장 상태 정보 조회"""
        # KIS API로 상세 정보 조회 (현재가, 전일비 등)
        price = self.kis.get_current_price(symbol)
        return {
            "symbol": symbol,
            "regular_market_price": price,
            # 나머지는 추가 조회 필요하나 핵심은 가격
        }
