"""
스케줄러 모듈
"""
import schedule
import time
from datetime import datetime
import pytz
from config.settings import TRADING_START_HOUR, TRADING_END_HOUR, TRADING_TIMEZONE
from utils.logger import logger

class TradingScheduler:
    """거래 스케줄러"""
    
    def __init__(self):
        self.timezone = pytz.timezone(TRADING_TIMEZONE)
        self.is_trading_time = False
    
    def is_within_trading_hours(self) -> bool:
        """거래 시간 확인"""
        now = datetime.now(self.timezone)
        current_hour = now.hour
        
        # 오후 5시 ~ 새벽 5시
        if current_hour >= TRADING_START_HOUR or current_hour < TRADING_END_HOUR:
            return True
        return False
    
    def schedule_daily_tasks(self, trading_func, monitoring_func, force_close_func):
        """일일 거래 작업 스케줄링"""
        # 거래 시작 시간 (오후 5시)
        schedule.every().day.at("17:00").do(self._start_trading, trading_func)
        
        # 새벽 05:00 강제 청산
        schedule.every().day.at("05:00").do(force_close_func)
        
        # 거래 종료 시간 (새벽 5시)
        schedule.every().day.at("05:00").do(self._end_trading)
        
        # 모니터링 (1분마다)
        schedule.every(1).minutes.do(monitoring_func)
        
        logger.info("스케줄러 설정 완료")
    
    def _start_trading(self, trading_func):
        """거래 시작"""
        logger.info("거래 시간 시작")
        self.is_trading_time = True
        trading_func()
    
    def _end_trading(self):
        """거래 종료"""
        logger.info("거래 시간 종료")
        self.is_trading_time = False
    
    def run(self):
        """스케줄러 실행"""
        logger.info("스케줄러 시작")
        while True:
            schedule.run_pending()
            time.sleep(1)

