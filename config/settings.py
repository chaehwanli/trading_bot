"""
거래 봇 설정 파일
"""
import os
from dotenv import load_dotenv

load_dotenv()


# KIS (한국투자증권) 실전투자 API 설정
KIS_REAL_APP_KEY = os.getenv("KIS_API_KEY", "")
KIS_REAL_APP_SECRET = os.getenv("KIS_API_SECRET", "")
KIS_REAL_ACCOUNT_NO = os.getenv("KIS_CANO", "")
KIS_REAL_BASE_URL = os.getenv("KIS_REAL_BASE_URL", "https://openapi.koreainvestment.com:9443")

# KIS (한국투자증권) 모의투자 API 설정
KIS_PAPER_APP_KEY = os.getenv("KIS_PAPER_API_KEY", "")
KIS_PAPER_APP_SECRET = os.getenv("KIS_PAPER_API_SECRET", "")
KIS_PAPER_ACCOUNT_NO = os.getenv("KIS_PAPER_CANO", "")
KIS_PAPER_BASE_URL = os.getenv("KIS_PAPER_BASE_URL", "https://openapivts.koreainvestment.com:29443")

# 하위 호환성을 위한 기본값 (KisApi에서 분기 처리 권장)
KIS_APP_KEY = KIS_REAL_APP_KEY
KIS_APP_SECRET = KIS_REAL_APP_SECRET
KIS_ACCOUNT_NO = KIS_REAL_ACCOUNT_NO
KIS_BASE_URL = KIS_REAL_BASE_URL

# ========== Telegram 설정 ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ========== 거래소 API 설정 ==========
# 예시: Alpaca, Interactive Brokers 등
API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "https://paper-api.alpaca.markets")  # Paper trading URL

# ========== 거래 대상 ==========
# 원본 주식 코드를 기준으로 2x ETF LONG/SHORT를 스위칭
# 구조: {"ORIGINAL": 원본주식, "LONG": 2x 롱 ETF, "SHORT": 2x 숏 ETF}
TARGET_SYMBOLS = [
    {
        "ORIGINAL": "COIN",  # 원본 주식: BitCoin
        "LONG": "BTCL",      # 2x 롱 ETF: Direxion Daily BTC Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "BTCZ",      # 2x 숏 ETF: Direxion Daily BTC Bear 1X Shares
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: Tesla
        "LONG": "TSLL",      # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "TSLZ",     # 1x 숏 ETF: Direxion Daily TSLA Bear 1X Shares
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "AMZN",# 원본 주식: Amazon
        "LONG": "AMZU",  # 2x 롱 ETF: Direxion Daily AMZN Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "AMZD",     # 1x 숏 ETF: Direxion Daily AMZN Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "AMD",# 원본 주식: AMD
        "LONG": "AMUU",  # 2x 롱 ETF: Direxion Daily AMD Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "AMDD",     # 1x 숏 ETF: Direxion Daily AMD Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
        {
        "ORIGINAL": "NVDA",  # 원본 주식: Nvidia
        "LONG": "NVDX",      # 2x 롱 ETF: T-Rex 2X Long Nvidia Daily Target ETF
        "LONG_MULTIPLE": "2",
        "SHORT": "NVDQ",      # 2x 숏 ETF: T-Rex 2X Inverse Nvidia Daily Target ETF
        "SHORT_MULTIPLE": "-2"
    }
]

"""
TARGET_SYMBOLS = [
    {
        "ORIGINAL": "COIN",  # 원본 주식: BitCoin
        "LONG": "BTCL",      # 2x 롱 ETF: Direxion Daily BTC Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "BTCZ",      # 2x 숏 ETF: Direxion Daily BTC Bear 1X Shares
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: Tesla
        "LONG": "TSLL",      # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "TSLZ",      # 2x 숏 ETF: T-Rex 2x Inverse Tesla Daily Target ETF
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "NVDA",  # 원본 주식: Nvidia
        "LONG": "NVDX",      # 2x 롱 ETF: T-Rex 2X Long Nvidia Daily Target ETF
        "LONG_MULTIPLE": "2",
        "SHORT": "NVDQ",      # 2x 숏 ETF: T-Rex 2X Inverse Nvidia Daily Target ETF
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "GOOGL",  # 원본 주식: Google
        "LONG": "GGLL",      # 2x 롱 ETF: Direxion Daily GOOGL Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "GGLS",      # 1x 숏 ETF: Direxion Daily GOOGL Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
    {
        "ORIGINAL": "AAPL",  # 원본 주식: Apple
        "LONG": "AAPU",      # 2x 롱 ETF: Direxion Daily AAPL Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "AAPD",      # 1x 숏 ETF: Direxion Daily AAPL Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: Tesla
        "LONG": "TSLL",      # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "TSLS",     # 1x 숏 ETF: Direxion Daily TSLA Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
    {
        "ORIGINAL": "AMD",# 원본 주식: AMD
        "LONG": "AMUU",  # 2x 롱 ETF: Direxion Daily AMD Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "AMDD",     # 1x 숏 ETF: Direxion Daily AMD Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
    {
        "ORIGINAL": "AMZN",# 원본 주식: Amazon
        "LONG": "AMZU",  # 2x 롱 ETF: Direxion Daily AMZN Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "AMZD",     # 1x 숏 ETF: Direxion Daily AMZN Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "AVGO",# 원본 주식: Broadcom
        "LONG": "AVL",  # 2x 롱 ETF: Direxion Daily AVGO Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "AVS",     # 1x 숏 ETF: Direxion Daily AVGO Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "META",# 원본 주식: Meta
        "LONG": "METU",  # 2x 롱 ETF: Direxion Daily META Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "METD",     # 1x 숏 ETF: Direxion Daily META Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "NFLX",# 원본 주식: Netflix
        "LONG": "NFXL",  # 2x 롱 ETF: Direxion Daily NFLX Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "NFXS",     # 1x 숏 ETF: Direxion Daily NFLX Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "TSLA",# 원본 주식: Tesla
        "LONG": "TSLT",  # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "TSLZ",     # 1x 숏 ETF: Direxion Daily TSLA Bear 1X Shares
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: BitCoin
        "LONG": "BTCL",      # 2x 롱 ETF: Direxion Daily BTC Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "BTCZ",      # 2x 숏 ETF: Direxion Daily BTC Bear 1X Shares
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: Tesla
        "LONG": "TSLL",      # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "TSLZ",      # 2x 숏 ETF: T-Rex 2x Inverse Tesla Daily Target ETF
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: Nvidia
        "LONG": "NVDX",      # 2x 롱 ETF: T-Rex 2X Long Nvidia Daily Target ETF
        "LONG_MULTIPLE": "2",
        "SHORT": "NVDQ",      # 2x 숏 ETF: T-Rex 2X Inverse Nvidia Daily Target ETF
        "SHORT_MULTIPLE": "-2"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: Google
        "LONG": "GGLL",      # 2x 롱 ETF: Direxion Daily GOOGL Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "GGLS",      # 1x 숏 ETF: Direxion Daily GOOGL Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: Apple
        "LONG": "AAPU",      # 2x 롱 ETF: Direxion Daily AAPL Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "AAPD",      # 1x 숏 ETF: Direxion Daily AAPL Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
    {
        "ORIGINAL": "TSLA",  # 원본 주식: Tesla
        "LONG": "TSLL",      # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
        "LONG_MULTIPLE": "2",
        "SHORT": "TSLS",     # 1x 숏 ETF: Direxion Daily TSLA Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
    {
        "ORIGINAL": "TSLA",# 원본 주식: AMD
        "LONG": "AMUU",  # 2x 롱 ETF: Direxion Daily AMD Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "AMDD",     # 1x 숏 ETF: Direxion Daily AMD Bear 1X Shares
        "SHORT_MULTIPLE": "-1"
    },
    {
        "ORIGINAL": "TSLA",# 원본 주식: Amazon
        "LONG": "AMZU",  # 2x 롱 ETF: Direxion Daily AMZN Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "AMZD",     # 1x 숏 ETF: Direxion Daily AMZN Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "TSLA",# 원본 주식: Broadcom
        "LONG": "AVL",  # 2x 롱 ETF: Direxion Daily AVGO Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "AVS",     # 1x 숏 ETF: Direxion Daily AVGO Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "TSLA",# 원본 주식: Meta
        "LONG": "METU",  # 2x 롱 ETF: Direxion Daily META Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "METD",     # 1x 숏 ETF: Direxion Daily META Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "TSLA",# 원본 주식: Netflix
        "LONG": "NFXL",  # 2x 롱 ETF: Direxion Daily NFLX Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "NFXS",     # 1x 숏 ETF: Direxion Daily NFLX Bear 1X Shares
        "SHORT_MULTIPLE": "-1"  
    },
    {
        "ORIGINAL": "TSLA",# 원본 주식: Tesla
        "LONG": "TSLT",  # 2x 롱 ETF: Direxion Daily TSLA Bull 2X Shares
        "LONG_MULTIPLE" : "2",
        "SHORT": "TSLZ",     # 1x 숏 ETF: Direxion Daily TSLA Bear 1X Shares
        "SHORT_MULTIPLE": "-2"
    }

    # 추가 종목 예시:
    # {
    #     "ORIGINAL": "AMD",
    #     "LONG": "AMDL",      # GraniteShares 2x Long AMD Daily ETF
    #     "LONG_MULTIPLE": 2,
    #     "SHORT": "AMDS"      # (숏 ETF가 있다면)
    #     "SHORT_MULTIPLE": -1
    # }
]
"""

# 편의 함수: 모든 ETF 심볼 리스트 반환
def get_all_etf_symbols():
    """모든 ETF 심볼 리스트 반환 (LONG + SHORT)"""
    symbols = []
    for item in TARGET_SYMBOLS:
        symbols.append(item["LONG"])
        symbols.append(item["SHORT"])
    return symbols

# 편의 함수: 원본 주식 코드 리스트 반환
def get_original_symbols():
    """원본 주식 코드 리스트 반환"""
    return [item["ORIGINAL"] for item in TARGET_SYMBOLS]

# 편의 함수: 원본 주식으로 ETF 정보 찾기
def get_etf_by_original(original_symbol: str):
    """원본 주식 코드로 ETF 정보 찾기"""
    for item in TARGET_SYMBOLS:
        if item["ORIGINAL"] == original_symbol:
            return item
    return None

# ========== 거래 시간 설정 ==========
TRADING_START_HOUR = 17  # 오후 5시 (한국시간 기준)
TRADING_END_HOUR = 5     # 새벽 5시 (익일)
TRADING_TIMEZONE = "Asia/Seoul"

# ========== 손익 기준 ==========
# 사용자 원안
STOP_LOSS_PCT = -0.02    # -2% (사용자 원안)
TAKE_PROFIT_PCT = 0.08   # +8% (사용자 원안)

# 권장 파라미터 (옵션)
STOP_LOSS_PCT_RECOMMENDED = -0.03    # -3% ~ -4% (슬리피지/레버리지 특성 보정)
TAKE_PROFIT_PCT_RECOMMENDED = 0.06   # +6% ~ +7%

# 현재 사용할 파라미터 선택
USE_RECOMMENDED = False  # True면 권장 파라미터 사용
STOP_LOSS = STOP_LOSS_PCT_RECOMMENDED if USE_RECOMMENDED else STOP_LOSS_PCT
TAKE_PROFIT = TAKE_PROFIT_PCT_RECOMMENDED if USE_RECOMMENDED else TAKE_PROFIT_PCT

# ========== 자금 관리 ==========
INITIAL_CAPITAL_MIN = 1200   # $1,200
INITIAL_CAPITAL_MAX = 2500   # $2,500
MAX_LOSS_PER_TRADE = 50      # $50

# ========== 포지션 사이징 (기대수익 기준) ==========
EXPECTED_PROFIT_MIN = 100    # $100 (최소 기대수익)
EXPECTED_PROFIT_MAX = 200    # $200 (최대 기대수익)
EXPECTED_PROFIT_TARGET = 150 # $150 (목표 기대수익)

# ========== 포지션 관리 ==========
MAX_POSITION_HOLD_DAYS = 2.0  # Long 최대 2일 보유
FORCE_CLOSE_HOUR = 7           # 새벽 05:00 강제 청산 (한국시간)
SHORT_SAME_DAY_CLOSE = True    # Short 당일 청산 필수

# ========== 기술적 지표 설정 ==========
RSI_PERIOD = 5
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_MIDDLE = 50

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

# ========== 전환 매매 전략 파라미터 (Reverse/Flip Trading Strategy) ==========

# 1. 기본 거래 파라미터
REVERSAL_SYMBOL = "TSLA"  # 거래 종목 (원본 주식)
REVERSAL_POSITION_TYPE = "NONE"  # 현재 포지션 상태: LONG, SHORT, NONE
REVERSAL_CAPITAL = 1200  # 전체 투자 시드 (USD)

# 2. 리스크 관리 파라미터
REVERSAL_STOP_LOSS_RATE = -0.03  # 손절 비율 (-2%)
REVERSAL_1X_STOP_LOSS_RATE = -0.03  # 손절 비율 (-2%)
REVERSAL_2X_STOP_LOSS_RATE = -0.08  # 손절 비율 (-8%)
REVERSAL_TAKE_PROFIT_RATE = 0.35  # 익절 비율 (+8%)
REVERSAL_LOMG_MAX_HOLD_DAYS = 5  # 포지션 유지 최대 기간
REVERSAL_SHORT_MAX_HOLD_DAYS = 1  # 포지션 유지 최대 기간
REVERSAL_MAX_HOLD_DAYS = 3  # 포지션 유지 최대 기간
REVERSAL_MAX_DRAWDOWN = 0.1  # 허용 최대 자본 손실률 (5%)
REVERSAL_REVERSE_TRIGGER = True  # 손절 후 반대 포지션 진입 트리거
REVERSAL_TRAILING_STOP = True  # 변동성 추종형 손절 설정

# 3. 시장 데이터 및 조건 파라미터
REVERSAL_LOOKBACK_WINDOW = 5  # 분석할 과거 데이터 일수
REVERSAL_VOLATILITY_THRESHOLD = 0.1  # 변동성 기준 (3%)
REVERSAL_PRICE_MOMENTUM = 0.02  # 가격 모멘텀 (전일 대비 상승률 2%)
REVERSAL_VOLUME_THRESHOLD = 0.4  # 거래량 기준치 (1.5배)
REVERSAL_MARKET_SENTIMENT_INDEX = 0.0  # 시장 심리지수 (-0.3 ~ +0.3)

# 4. 전환 로직 파라미터
REVERSAL_REVERSE_MODE = "full"  # 전환 방식: 'full'(전체 반전), 'partial'(부분 반전)
REVERSAL_REVERSE_DELAY = 5  # 손절 후 반전 진입 지연 시간 (초)
REVERSAL_REVERSE_CONFIRMATION = True  # 반전 진입 전 추가 확인 조건
REVERSAL_REVERSE_RISK_FACTOR = 0.8  # 반전시 진입 자본 비율 (기존보다 80%)
REVERSAL_COOLDOWN_PERIOD = 1  # 반전 후 추가 거래 금지 기간 (일)
REVERSAL_REVERSAL_LIMIT = 1 # 24시간내 최대 전환 횟수

# 5. 로그 및 모니터링 파라미터
REVERSAL_LOG_LEVEL = "INFO"  # 로그 상세도: DEBUG, INFO, WARN
REVERSAL_ALERT_CHANNEL = None  # 알림 수단: Telegram, Slack 등
REVERSAL_RECORD_TRADES = True  # 거래 기록 저장 여부

# 전환 매매 전략 파라미터 딕셔너리 (편의용)
REVERSAL_STRATEGY_PARAMS = {
    "symbol": REVERSAL_SYMBOL,
    "capital": REVERSAL_CAPITAL,
    "stop_loss_rate": REVERSAL_STOP_LOSS_RATE,
    "1x_stop_loss_rate": REVERSAL_1X_STOP_LOSS_RATE,
    "2x_stop_loss_rate": REVERSAL_2X_STOP_LOSS_RATE,
    "take_profit_rate": REVERSAL_TAKE_PROFIT_RATE,
    "reverse_trigger": REVERSAL_REVERSE_TRIGGER,
    "reverse_mode": REVERSAL_REVERSE_MODE,
    "reverse_delay": REVERSAL_REVERSE_DELAY,
    "reverse_risk_factor": REVERSAL_REVERSE_RISK_FACTOR,
    "long_max_hold_days": REVERSAL_LOMG_MAX_HOLD_DAYS,
    "short_max_hold_days": REVERSAL_SHORT_MAX_HOLD_DAYS,
    "lookback_window": REVERSAL_LOOKBACK_WINDOW,
    "volatility_threshold": REVERSAL_VOLATILITY_THRESHOLD,
    "cooldown_period": REVERSAL_COOLDOWN_PERIOD,
    "reversal_limit": REVERSAL_REVERSAL_LIMIT,
    "max_drawdown": REVERSAL_MAX_DRAWDOWN,
    "trailing_stop": REVERSAL_TRAILING_STOP,
    "reverse_confirmation": REVERSAL_REVERSE_CONFIRMATION,
    "price_momentum": REVERSAL_PRICE_MOMENTUM,
    "volume_threshold": REVERSAL_VOLUME_THRESHOLD,
    "market_sentiment_index": REVERSAL_MARKET_SENTIMENT_INDEX,
    "rsi_oversold": 50,
}

