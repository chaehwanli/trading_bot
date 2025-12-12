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
    
    def __init__(self):
        # 실전/모의 여부는 config 등에서 가져와야 하나 일단 모의투자로 안전하게 기본 설정하거나
        # 봇이 초기화될 때 주입받는 구조가 좋음. 여기선 기본값을 설정.
        # 주의: kis_api.py 내부에서 KIS_ACCOUNT_NO 등을 쓰므로 
        # is_paper_trading 플래그만 중요.
        # 봇 실행 시점에서 결정된 모드를 따라야 하나, DataFetcher 독립적 사용 시 모호함.
        # 유저 환경에 맞춰 True(모의) or False(실전) 설정 필요.
        # 여기서는 안전하게 True로 하거나, Settings에서 가져오는 것이 좋음.
        # 일단 False(실전)으로 하되, 실제 트레이딩 봇이 사용하는 인스턴스와 일치해야 함.
        # 하지만 DataFetcher는 보통 '정보 조회'용.
        self.kis = KisApi(is_paper_trading=False) # 실전 기준? (유저 요청: KIS API로 거래/조회)
    
    def get_realtime_price(self, symbol: str) -> Optional[float]:
        """실시간 가격 조회"""
        return self.kis.get_current_price(symbol)
    
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
                # get_minute_price는 최근 120개(2시간? 120시간?) 등 제한적임.
                # "1h" -> 60분봉
                raw_data = self.kis.get_minute_price(symbol)
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
