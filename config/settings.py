"""
거래 봇 설정 파일
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ========== 거래소 API 설정 ==========
# 예시: Alpaca, Interactive Brokers 등
API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "https://paper-api.alpaca.markets")  # Paper trading URL

# ========== 거래 대상 ==========
TARGET_SYMBOLS = [
    "TQQQ",  # 0 - NASDAQ-100 3배 레버리지 (2배 대신 3배 사용 가능)
    "SQQQ",  # 1- NASDAQ-100 역방향 3배 레버리지
    "TSLL",  # 2- Direxion Daily TSLA Bull 2X Shares
    "TSLZ",  # 3- T-Rex 2x Inverse Tesla Daily Target ETF
    "NVDX",  # 4- T-Rex 2X Long Nvidia Daily Target ETF
    "NVDQ",  # 5- T-Rex 2X Inverse Nvidia Daily Target ETF
    "AMDL"   # 6- GraniteShares 2x Long AMD Daily ETF
]
# ========== 거래 시간 설정 ==========
TRADING_START_HOUR = 17  # 오후 5시 (한국시간 기준)
TRADING_END_HOUR = 5     # 새벽 5시 (익일)
TRADING_TIMEZONE = "Asia/Seoul"

# ========== 손익 기준 ==========
STOP_LOSS_PCT = -0.03    # -3%
TAKE_PROFIT_MIN_PCT = 0.06  # +6%
TAKE_PROFIT_MAX_PCT = 0.07  # +7%

# ========== 자금 관리 ==========
INITIAL_CAPITAL_MIN = 1200   # $1,200
INITIAL_CAPITAL_MAX = 2500   # $2,500
MAX_LOSS_PER_TRADE = 50      # $50

# ========== 포지션 관리 ==========
MAX_POSITION_HOLD_DAYS = 1.5  # 최대 1.5일
FORCE_CLOSE_HOUR = 9          # 익일 오전 9시 강제 매도

# ========== 기술적 지표 설정 ==========
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ========== 거래 설정 ==========
POSITION_SIZE_PCT = 0.95  # 사용 가능 자금의 95% 사용
MIN_TRADE_AMOUNT = 100    # 최소 거래 금액

# ========== 로깅 설정 ==========
LOG_LEVEL = "INFO"
LOG_FILE = "trading_bot.log"

# ========== 테스트 모드 ==========
PAPER_TRADING = True  # Paper trading 모드
DRY_RUN = False       # 실제 주문 없이 시뮬레이션만

