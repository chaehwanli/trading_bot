"""
시장 데이터 수집 모듈
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import logger
from database.db_manager import DatabaseManager

class DataFetcher:
    """시장 데이터 수집 클래스"""
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = timedelta(minutes=1)  # 1분 캐시
        self.db_manager = DatabaseManager()
    
    def get_realtime_price(self, symbol: str) -> Optional[float]:
        """실시간 가격 조회"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")
            
            if data.empty:
                logger.warning(f"{symbol}: 데이터 없음")
                return None
            
            latest_price = data['Close'].iloc[-1]
            logger.debug(f"{symbol} 현재가: ${latest_price:.2f}")
            return float(latest_price)
            
        except Exception as e:
            logger.error(f"{symbol} 가격 조회 실패: {e}")
            return None
    
    def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1mo",
        interval: str = "1h"
    ) -> Optional[pd.DataFrame]:
        """과거 데이터 조회"""
        try:
            # 1. DB에서 데이터 조회 시도
            # period를 날짜 범위로 변환 (휴일/주말 고려하여 여유있게 설정)
            end_date = datetime.now()
            start_date = None
            
            if period == "1d":
                start_date = end_date - timedelta(days=2)
            elif period == "5d":
                start_date = end_date - timedelta(days=10) # 주말 포함 넉넉하게
            elif period == "1mo":
                start_date = end_date - timedelta(days=45)
            elif period == "3mo":
                start_date = end_date - timedelta(days=100)
            elif period == "6mo":
                start_date = end_date - timedelta(days=200)
            elif period == "1y":
                start_date = end_date - timedelta(days=400)
            # 다른 기간은 API 직접 호출로 처리 (구현 복잡성 감소)

            if start_date:
                # DB에서 조회 시 start_date보다 이후 데이터를 가져오되, 
                # API 호출 결과("5d")와 비슷하게 맞추기 위해 
                # 가져온 데이터 중 가장 최근 데이터까지 끊기보다는 
                # 일단 범위 내 데이터를 다 가져옴.
                # 단, 여기서 start_date는 DB 쿼리용 필터임.
                
                db_data = self.db_manager.get_historical_data(symbol, interval, start_date, end_date)
                
                if db_data is not None and not db_data.empty:
                    # 데이터가 충분한지 간단히 확인 (행 수 기준 등으로 정교화 가능하나 일단 존재 여부로 판단)
                    # "5d" 요청시 API가 35개를 주는데 DB에서 10일치 조회하면 더 많이 나올 수 있음
                    # -> API "5d"는 '최근 5거래일'을 의미.
                    # DB에서 가져온 데이터가 너무 적으면(예: 1개) API 호출 필요
                    
                    min_rows = 5 # 최소 데이터 개수 기준 (임의 설정)
                    if period == "1d": min_rows = 1
                    
                    if len(db_data) >= min_rows:
                        # yfinance "5d"는 최근 5거래일만 리턴하므로, DB에서 너무 옛날 데이터까지 가져오면 결과가 다를 수 있음
                        # 하지만 user requirement: "과거 데이터를 DB에 저장하고 DB에서 조건에 맞는 데이터가 없으면..."
                        # 즉 DB에 있으면 DB 데이터 쓰라는 것.
                        # DB 데이터가 더 많으면 좋은 것 (cache hit). 
                        # 다만 API "5d" 요청했을 때의 기대값(최근 5일)에 맞춰 잘라줄 필요가 있는지?
                        # 기간('period') 파라미터는 yfinance spec.
                        # 여기서는 DB 데이터를 그대로 반환하되, 너무 오래된 데이터는 필터링할 수도 있음.
                        # 지금은 그대로 반환.
                        logger.debug(f"{symbol} DB에서 데이터 로드: {len(db_data)}개 (기간: {period})")
                        return db_data

            # 2. API에서 데이터 조회
            logger.info(f"{symbol} API에서 데이터 다운로드 중... (기간: {period})")
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                logger.warning(f"{symbol}: 과거 데이터 없음")
                return None
            
            # 컬럼명 정리
            data.columns = [col.lower().replace(' ', '_') for col in data.columns]
            
            # 3. DB에 저장
            self.db_manager.save_historical_data(data, symbol, interval)
            
            logger.debug(f"{symbol} 과거 데이터 조회 및 저장 성공: {len(data)}개")
            return data
            
        except Exception as e:
            logger.error(f"{symbol} 과거 데이터 조회 실패: {e}")
            return None
    
    def get_intraday_data(
        self, 
        symbol: str, 
        interval: str = "5m"
    ) -> Optional[pd.DataFrame]:
        """당일 분봉 데이터 조회"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval=interval)
            
            if data.empty:
                return None
            
            data.columns = [col.lower().replace(' ', '_') for col in data.columns]
            return data
            
        except Exception as e:
            logger.error(f"{symbol} 분봉 데이터 조회 실패: {e}")
            return None
    
    def get_market_status(self, symbol: str) -> Dict[str, any]:
        """시장 상태 정보 조회"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                "symbol": symbol,
                "market_state": info.get("marketState", "UNKNOWN"),
                "regular_market_price": info.get("regularMarketPrice"),
                "previous_close": info.get("previousClose"),
                "volume": info.get("volume"),
            }
        except Exception as e:
            logger.error(f"{symbol} 시장 상태 조회 실패: {e}")
            return {}

