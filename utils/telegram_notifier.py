import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Telegram 알림 발송 유틸리티"""
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        
        if not self.token or not self.chat_id:
            logger.warning("Telegram Bot Token 또는 Chat ID가 설정되지 않았습니다. 알림이 발송되지 않습니다.")

    def send_message(self, message: str) -> bool:
        """일반 메시지 발송"""
        if not self.token or not self.chat_id:
            return False
            
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML" # HTML 포맷 지원
            }
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram 메시지 발송 실패: {e}")
            return False

    def send_order_alert(self, symbol: str, side: str, price: float, quantity: float, reason: str = ""):
        """주문 체결 알림"""
        emoji = "📈" if side.upper() == "BUY" else "📉"
        # 사이드 표시: BUY(매수), SELL(매도)
        side_kr = "매수" if side.upper() == "BUY" else "매도"
        
        message = (
            f"{emoji} <b>[주문 알림] {symbol} {side_kr}</b>\n\n"
            f"• 가격: <code>${price:.2f}</code>\n"
            f"• 수량: <code>{quantity}</code>\n"
            f"• 사유: {reason}\n"
            f"• 시간: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def send_error_alert(self, error_msg: str):
        """에러 알림"""
        message = (
            f"🚨 <b>[오류 발생]</b>\n\n"
            f"{error_msg}\n"
            f"• 시간: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def send_strategy_update(self, 
                             symbol: str, 
                             market_status: str, 
                             signal: str, 
                             confidence: float, 
                             current_position: Optional[str], 
                             action: str,
                             rsi: Optional[float] = None,
                             macd: Optional[dict] = None):
        """전략 실행 결과 알림"""
        
        # 신호에 따른 이모지
        signal_emoji = "⚪"
        if "BUY" in str(signal).upper(): signal_emoji = "🟢"
        elif "SELL" in str(signal).upper(): signal_emoji = "🔴"
        
        # 지표 정보 포맷팅
        indicators_info = ""
        if rsi is not None:
             indicators_info += f"• RSI: {rsi:.2f}\n"
        if macd is not None:
             # MACD, Signal, Hist
             indicators_info += f"• MACD: {macd.get('macd',0):.2f} / Sig: {macd.get('signal',0):.2f}"
        
        message = (
            f"📊 <b>[전략 실행 결과] {symbol}</b>\n\n"
            f"• 장 상태: {market_status}\n"
            f"• 현재 포지션: {current_position if current_position else '없음'}\n"
            f"• 신호: {signal_emoji} {signal} (확률: {confidence:.2f})\n"
            f"{indicators_info}\n"
            f"• 결정: {action}\n"
            f"• 시간: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)
