import os
import sys
from dotenv import load_dotenv

# 현재 디렉토리 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.telegram_notifier import TelegramNotifier

def test_telegram():
    # .env 파일 로드
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"Token: {token[:5]}..." if token else "Token: None")
    print(f"Chat ID: {chat_id}" if chat_id else "Chat ID: None")
    
    if not token or not chat_id:
        print("❌ .env 파일에 TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        return

    print("🚀 Telegram 테스트 메시지 전송 시도...")
    notifier = TelegramNotifier(token=token, chat_id=chat_id)
    
    # 일반 메시지 테스트
    success = notifier.send_message("🔔 <b>테스트 메시지</b>\n이 메시지가 보이면 설정이 완료된 것입니다.")
    
    if success:
        print("✅ 메시지 전송 성공! Telegram을 확인하세요.")
        
        # 에러 알림 테스트 (선택)
        print("🚀 에러 알림 테스트...")
        notifier.send_error_alert("테스트 에러가 발생했습니다.")
    else:
        print("❌ 메시지 전송 실패. 토큰과 채팅 ID를 확인하세요.")

if __name__ == "__main__":
    test_telegram()
