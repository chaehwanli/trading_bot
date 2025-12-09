import sqlite3
import pandas as pd
from datetime import datetime
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import logger

class DatabaseManager:
    def __init__(self, db_path="trading_bot.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """데이터베이스 및 테이블 초기화"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 과거 데이터 테이블 생성
                # symbol, interval, timestamp를 복합 키로 설정하여 중복 방지
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS historical_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        interval TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume REAL,
                        dividends REAL,
                        stock_splits REAL,
                        UNIQUE(symbol, interval, timestamp)
                    )
                """)
                conn.commit()
                logger.info("데이터베이스 초기화 완료")
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")

    def save_historical_data(self, data: pd.DataFrame, symbol: str, interval: str):
        """과거 데이터 저장"""
        try:
            if data.empty:
                return

            # DataFrame을 DB에 저장하기 위해 가공
            df_to_save = data.copy()
            
            # 인덱스가 timestamp인 경우 컬럼으로 변환
            if isinstance(df_to_save.index, pd.DatetimeIndex):
                df_to_save = df_to_save.reset_index()
            
            # 컬럼명 소문자로 변경 (yfinance에서 Date/Datetime으로 옴)
            df_to_save.columns = [col.lower() for col in df_to_save.columns]
            
            # timestamp 컬럼 이름 통일 ('date' -> 'timestamp' or 'datetime' -> 'timestamp')
            if 'date' in df_to_save.columns:
                df_to_save.rename(columns={'date': 'timestamp'}, inplace=True)
            elif 'datetime' in df_to_save.columns:
                df_to_save.rename(columns={'datetime': 'timestamp'}, inplace=True)

            # 필요한 컬럼만 선택 및 추가
            df_to_save['symbol'] = symbol
            df_to_save['interval'] = interval
            
            # 필수 컬럼 확인
            required_cols = ['symbol', 'interval', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df_to_save.columns:
                    logger.warning(f"필수 컬럼 누락: {col}")
                    continue

            # DB에 저장 (UPSERT 방식 사용 - SQLite 3.24+ 지원)
            # 여기서는 간단하게 INSERT OR IGNORE 사용
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 배치 처리를 위한 데이터 준비
                records = []
                for _, row in df_to_save.iterrows():
                    records.append((
                        row['symbol'],
                        row['interval'],
                        row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'), # datetime 객체를 문자열로 변환
                        row['open'],
                        row['high'],
                        row['low'],
                        row['close'],
                        row['volume'],
                        row.get('dividends', 0),
                        row.get('stock_splits', 0)
                    ))

                cursor.executemany("""
                    INSERT OR IGNORE INTO historical_data 
                    (symbol, interval, timestamp, open, high, low, close, volume, dividends, stock_splits)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, records)
                conn.commit()
                
            logger.debug(f"{symbol} 데이터 {len(records)}건 DB 저장 완료")
            
        except Exception as e:
            logger.error(f"DB 저장 실패: {e}")

    def get_historical_data(self, symbol: str, interval: str, start_date: datetime = None, end_date: datetime = None) -> pd.DataFrame:
        """DB에서 과거 데이터 조회"""
        try:
            query = "SELECT * FROM historical_data WHERE symbol = ? AND interval = ?"
            params = [symbol, interval]

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.strftime('%Y-%m-%d %H:%M:%S'))
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.strftime('%Y-%m-%d %H:%M:%S'))

            query += " ORDER BY timestamp ASC"

            with self._get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=params)

            if df.empty:
                return None

            # timestamp를 인덱스로 설정 및 타입 변환
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # 불필요한 컬럼 제거 (id, symbol, interval)
            df.drop(columns=['id', 'symbol', 'interval'], inplace=True, errors='ignore')
            
            return df

        except Exception as e:
            logger.error(f"DB 조회 실패: {e}")
            return None
