import json
import os
from datetime import datetime, date
from utils.logger import logger

STATE_FILE = "bot_state.json"

class TradeStateManager:
    """봇 상태(매매 정보) 영구 저장 관리자"""
    
    def __init__(self, state_file=STATE_FILE):
        self.state_file = state_file

    def save_state(self, state_data: dict):
        """상태 저장"""
        try:
            # datetime 객체 직렬화 처리
            serializable_data = {}
            for k, v in state_data.items():
                if isinstance(v, (datetime, date)):
                    serializable_data[k] = v.isoformat()
                else:
                    serializable_data[k] = v
            
            # 절대 경로 사용이 안전할 수 있으나, 실행 위치 기준 루트에 저장
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=4, ensure_ascii=False)
            logger.info("봇 상태 저장 완료")
        except Exception as e:
            logger.error(f"봇 상태 저장 실패: {e}")

    def load_state(self):
        """상태 로드"""
        if not os.path.exists(self.state_file):
            return None
            
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # datetime 복원
            if 'entry_time' in data and data['entry_time']:
                try:
                    data['entry_time'] = datetime.fromisoformat(data['entry_time'])
                except ValueError:
                    pass # 문자열 그대로 유지

            # date 복원 (force_close_date, cooldown_until_date)
            for date_field in ['force_close_date', 'cooldown_until_date']:
                if date_field in data and data[date_field]:
                    try:
                        data[date_field] = datetime.fromisoformat(data[date_field]).date()
                    except ValueError:
                        try: 
                            data[date_field] = datetime.strptime(data[date_field], "%Y-%m-%d").date()
                        except:
                            pass
                    
            # date 복원 (cooldown_until_date)
            if 'cooldown_until_date' in data and data['cooldown_until_date']:
                try:
                    data['cooldown_until_date'] = datetime.fromisoformat(data['cooldown_until_date']).date()
                except ValueError:
                    try:
                        data['cooldown_until_date'] = datetime.strptime(data['cooldown_until_date'], "%Y-%m-%d").date()
                    except:
                        pass
                    
            return data
        except Exception as e:
            logger.error(f"봇 상태 로드 실패: {e}")
            return None

    def clear_state(self):
        """상태 초기화 (파일 삭제 or 빈 값 저장)"""
        try:
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
                logger.info("봇 상태 파일 삭제 (초기화)")
        except Exception as e:
            logger.error(f"봇 상태 초기화 실패: {e}")
