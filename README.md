# 미국 대형주 2배 레버리지 ETF 자동매매 봇

## 프로젝트 개요
테슬라(TSLA), 엔비디아(NVDA) 등 미국 대형주 2배 레버리지 ETF를 대상으로 하는 자동매매 시스템

## 주요 기능
- **운용주기**: Daily (오후 5시 ~ 새벽 5시)
- **손익 기준**: 손절 -3%, 익절 +6~7%
- **기대수익**: 하루 1~3% 목표
- **포지션 관리**: 최대 1.5일 유지 (익일 오전 매도)
- **기술적 지표**: RSI/MACD 기반 매매 신호
- **자동 매도**: 조건형 트리거 (가격 기준)

## 프로젝트 구조
```
trading_bot/
├── config/
│   └── settings.py          # 설정 파일
├── data/
│   └── data_fetcher.py      # 데이터 수집 모듈
├── strategy/
│   └── indicators.py        # 기술적 지표 계산
│   └── signal_generator.py # 매매 신호 생성
├── trading/
│   └── trader.py            # 거래 실행 모듈
│   └── position_manager.py  # 포지션 관리
├── utils/
│   └── logger.py            # 로깅 유틸리티
│   └── scheduler.py         # 스케줄러
├── main.py                  # 메인 봇 실행 파일
├── test_bot.py              # 테스트 코드
└── requirements.txt         # 의존성 패키지
```

## 설치 방법
```bash
cd ~/trading_bot
pip install -r requirements.txt
```

## 설정
`config/settings.py`에서 API 키 및 거래 설정을 수정하세요.

## 실행 방법
```bash
# 테스트 모드
python test_bot.py

# 실제 거래 모드
python main.py
```

## 주의사항
- 실제 거래 전 반드시 모의 거래로 테스트하세요
- API 키는 안전하게 관리하세요
- 레버리지 거래는 고위험 투자입니다

