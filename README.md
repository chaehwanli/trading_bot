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
│   └── reversal_strategy.py # 전환 매매 전략
│   └── signal_generator.py # 매매 신호 생성
├── trading/
│   └── trader.py            # 거래 실행 모듈
│   └── position_manager.py  # 포지션 관리
├── utils/
│   └── logger.py            # 로깅 유틸리티
│   └── scheduler.py         # 스케줄러
├── main.py                  # 메인 봇 실행 파일
├── test_bot.py              # 테스트 코드
├── reversal_backtest.py     # 백테스트 코드
├── reversal_trading_bot.py  # 실제 거래 코드
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
# backtest
python reversal_backtest.py
# 테스트 모드
python test_bot.py

# 실제 거래 모드
python main.py
```

## 주의사항
- 실제 거래 전 반드시 모의 거래로 테스트하세요
- API 키는 안전하게 관리하세요
- 레버리지 거래는 고위험 투자입니다

## Result
Check "result.txt" for more details

## 한국 투자 증권의 미국장 거래 시간
 한국 투자 증권의 미국장 거래 시간이 고려되어야 함.
  -. 주간거래(장전거래) 10:00 ~18:00
     Summer Time : 10:00 ~ 17:00
  -. 프리마켓(장전거래) 18:00 ~ 23:30 
     Summer Time : 17:00 ~ 22:30
  -. 정규장 :23:30 ~06:00
     Summer Time : 22:30 ~ 05:00
  -. 애프터마켓(정규장 종료 후 거래) : 06:00 ~07:00
     Summer Time : 05:00 ~ 07:00
  -. 애프터마켓 연장신청시 (정규장 종류후 거래) : 07:00 ~ 09:00
     Summer Time : 07:00 ~ 09:00
  -. 미국 Summer Time 고려해야 함.


## Type Classification
아래 내용은 **기술지표 흐름(RSI/MACD)**, **변동성 특성**, **스윙 가능성(추세 전환 패턴)** 관점에서
테슬라(TSLA), 엔비디아(NVDA), 애플(AAPL), 구글(GOOGL), AMD 다섯 종목의 **유형화(Type Classification)** 정리임.
데이터 수치는 넣지 않고 **전형적인 패턴 분석** 위주로 작성함.

---

# 📌 5개 빅테크/고변동 종목의 기술적 패턴 유형별 비교

## 전체 비교표 요약

| 종목                 | 변동성   | RSI 패턴     | MACD 패턴      | 스윙 빈도    | 전략 유형            |
| ------------------ | ----- | ---------- | ------------ | -------- | ---------------- |
| **Tesla (TSLA)**   | 매우 높음 | 과매수/과매도 빈번 | 골든/데드 전환 잦음  | 매우 빈번    | 모멘텀·뉴스 기반 변동 플레이 |
| **NVIDIA (NVDA)**  | 높음    | 과매수 강도 높음  | 중기 상승 모멘텀 강함 | 중간       | 추세 추종형에 유리       |
| **Apple (AAPL)**   | 낮음~중간 | RSI 과열 적음  | MACD 완만      | 스윙 적음    | 안정적 / 장기 추세 추종   |
| **Google (GOOGL)** | 낮음~중간 | 과열 신호 드묾   | MACD 급변 적음   | 스윙 낮음    | 안정적, 박스권 돌파형     |
| **AMD**            | 높음    | 과열·과매도 자주  | MACD 빠른 전환   | 스윙 매우 많음 | 모멘텀·스윙 트레이딩 적합   |

---

# 🔥 1. Tesla (TSLA)

**유형: 고변동·강모멘텀·뉴스 민감형**

### 🔹 기술지표 흐름 특징

* **RSI가 30~70보다 자주 바깥으로 벗어남**
  → 80 근처 과열, 20~30 과매도 구간 빈번
* 단기 수급·뉴스에 따라 “한 번에 크게 움직였다가 바로 되돌림” 패턴 흔함

### 🔹 MACD 특징

* 골든/데드 크로스 반복 주기가 빠름
* 히스토그램 폭이 큼 → 모멘텀 강도 변화가 뚜렷

### 🔹 변동성 & 스윙 성향

* Nasdaq 대형주 중 변동성 최상급
* **V자·역V자 스윙 패턴 자주 발생**
* 스윙 전략(L/S switching)에 가장 적합한 성향

---

# 🚀 2. NVIDIA (NVDA)

**유형: 고성장·강추세·과열 추세 지속형**

### 🔹 RSI 패턴 특징

* 상승 추세 구간에서 **RSI 70 이상에서도 오랫동안 유지**되는 특징
* 고평가 상태라도 추세가 지속되는 경우가 많음 → “RSI만 보고 역매매하면 털림”

### 🔹 MACD 패턴

* 중장기 상승구간에서 **MACD가 0선 위에서 계속 머무르는 트렌드형 구조**
* 데드크로스가 나와도 가격 조정이 짧은 경우多

### 🔹 변동성 & 스윙 성향

* Tesla보다 정교하고 안정된 변동
* **추세 추종 전략에 최적화**
* 스윙보다는 “상승 추세 지속”을 노리는 전략이 유효

---

# 🍎 3. Apple (AAPL)

**유형: 저변동·안정적·대형가치주 패턴**

### 🔹 RSI 패턴 특징

* RSI가 30·70 바깥으로 벗어나는 경우 매우 드묾
* 과열 신호가 나와도 상승 지속성이 낮음 → 조용한 기술적 패턴

### 🔹 MACD 패턴

* 크로스 발생 주기 느림
* 히스토그램 변화폭도 작음 → 모멘텀 약함

### 🔹 변동성 & 스윙 성향

* 스윙보다는 **박스권·우상향 장기추세**
* 추세 기반 전략보다 **브레이크아웃(돌파 전략)**이 더 적합
* L/S switching 전략에는 *덜 유리한 종목*

---

# 📘 4. Google (GOOGL)

**유형: 안정적·저변동·완만추세형**

### 🔹 RSI 패턴

* RSI 70/30 근처에 거의 접근하지 않음
* 과열 → 가격 조정 반응이 크지 않음
* RSI 신뢰도가 낮은 종목군

### 🔹 MACD 패턴

* 추세 전환이 매우 느림
* 중기 추세가 부드럽게 이어지는 형태

### 🔹 변동성 & 스윙 성향

* 스윙보다는 **‘평탄한 우상향’ or ‘박스권 유지’** 패턴
* 돌파 시 큰 움직임이 나오지만 빈도는 낮음

---

# 🔥 5. AMD

**유형: 고변동·재료 민감형·스윙 잦음(테슬라와 유사)**

### 🔹 RSI 패턴

* 변동성 높아서 RSI 범위를 자주 벗어남
* 과매수·과매도 구간 빈번 → Tesla와 가장 비슷함

### 🔹 MACD 패턴

* 모멘텀 변동이 빠르고 극단적
* MACD 히스토그램 급증/급감 흔함 → 모멘텀 기반 스윙에 적합

### 🔹 변동성 & 스윙 성향

* 단기 급등락 반복
* 재료(신제품, AI 뉴스, 실적)에 매우 민감
* **스윙 전략·단타 전략 모두 적합**

---

# 📌 전략 관점 요약 (Long/Short ETF Switching 시 고려)

| 종목        | 스위칭 전략 적합도 | 이유                                |
| --------- | ---------- | --------------------------------- |
| **TSLA**  | 매우 높음      | 변동성 + RSI/MACD 신호가 잘 작동, 스윙 빈도 최고 |
| **NVDA**  | 중간~높음      | 강한 추세 → 추세 스위칭 유효 but 역매매는 위험     |
| **AAPL**  | 낮음         | 변동성 낮아 L/S 스위칭 비효율                |
| **GOOGL** | 낮음         | 스윙 빈도 낮음, 기술적 신호 약함               |
| **AMD**   | 매우 높음      | 고변동 + 패턴 명확 → 스윙 기반 스위칭 효과적       |

---

# 🔍 결론 요약

### **테슬라와 스윙·기술지표 패턴이 가장 유사한 종목 = AMD**

* 변동성
* RSI 과열/과매도 빈도
* MACD 전환 반복
  이 세 가지 모두 TSLA와 가장 유사함.

### **추세 기반 전략에 강한 종목 = NVIDIA**

* 상승 모멘텀 유지력이 독보적

### **안정적, 신호 적음, 스윙 전략 비효율 = Apple & Google**

---

# Backtest Result Differences Analysis
## KIS vs YFinance Data Comparison
### Executive Summary
The backtest results differ significantly between KIS and YFinance data sources due to three main factors:

- Data Coverage: Different historical data ranges
- Timezone/Timestamp Alignment: Different data collection times
- Price Discrepancies: Different price values for the same symbols

## Key Findings
### 1. Data Coverage Difference
TSLA Example:
1. KIS Data: 384 rows

- Start: 2025-11-07 18:00:00+09:00
- End: 2025-12-13 08:00:00+09:00
- Coverage: ~1 month of data

2. YFinance Data: 1739 rows

- Start: 2024-12-13 23:30:00+09:00
- End: 2025-12-13 05:30:00+09:00
- Coverage: ~1 year of data

Impact: The backtest period (2025-11-17 ~ 2025-12-13) falls within different data availability:

- YFinance has full coverage for the backtest period
- KIS only has partial coverage starting from 2025-11-07

### 2. Timestamp Alignment Issues
KIS Data Pattern:
```
2025-11-07 18:00:00+09:00  (6:00 PM KST)
2025-11-07 19:00:00+09:00  (7:00 PM KST)
2025-11-07 20:00:00+09:00  (8:00 PM KST)

```
YFinance Data Pattern:
```
2024-12-13 23:30:00+09:00  (11:30 PM KST)
2024-12-14 00:30:00+09:00  (12:30 AM KST)
2024-12-14 01:30:00+09:00  (1:30 AM KST)
```

Observations:

- KIS data appears to be on the hour (18:00, 19:00, 20:00)
- YFinance data is on the half-hour (23:30, 00:30, 01:30)
- This 30-minute offset means they're capturing different market moments

### 3. Price Value Differences
TSLZ (Tesla Short ETF) Comparison:
KIS Data (2025-11-07 18:00):

- Open: 12.64
- High: 12.82
- Low: 12.48
- Close: 12.76

YFinance Data (2024-12-13 23:30):

- Open: 51.37
- High: 52.40
- Low: 48.80
- Close: 49.30

```
K 2025-11-12 00:00:00+09:00,438.8721,439.5,432.74,433.42,9798564,
10.62053469868734,0.5155770940693856,-1.46402665981691,1.9796037538862956

Y 2025-11-12 00:30:00+09:00,433.3699951171875,433.3699951171875,436.3999938964844,432.739990234375,435.3200073242188,8678369,
26.92263609827025,-2.3635850589855636,0.30251179877855705,-2.6660968577641206

K 2025-11-12 01:00:00+09:00,433.42,436.4,432.36,433.06,7310780,
10.1829006970735,-0.11911704148167246,-1.6789766362943745,1.559859594812702

Y 2025-11-12 01:30:00+09:00,433.9206848144531,433.9206848144531,435.4200134277344,432.3599853515625,433.3699951171875,6055282,
29.657285978991997,-2.6955341047456614,-0.023549797585232568,-2.671984307160429

K 2025-11-12 02:00:00+09:00,433.06,435.8,432.81,435.22,5083007,
31.387466866324214,-0.44271937513002513,-1.602063175954182,1.1593438008241568

Y 2025-11-12 02:30:00+09:00,435.8301086425781,435.8301086425781,436.7099914550781,433.2300109863281,433.9700012207031,5069321,
39.47400178968498,-2.7725710961346977,-0.08046943117941519,-2.6921016649552825

K 2025-11-12 03:00:00+09:00,435.22,437.03,434.0822,437.03,5098410,
44.99067942085976,-0.5468212675881432,-1.36493205472984,0.8181107871416968

Y 2025-11-12 03:30:00+09:00,437.375,437.375,437.7200012207031,434.0822143554688,435.8599853515625,4577265,
46.960098382124315,-2.678092264908571,0.011207520037369356,-2.6892997849459404

K 2025-11-12 04:00:00+09:00,437.03,437.85,435.65,436.23,4295961,
40.54907010912751,-0.6859686617637522,-1.2032635591243592,0.5172948973606071

Y 2025-11-12 04:30:00+09:00,436.9800109863281,436.9800109863281,437.8500061035156,436.0,437.3995056152344,4225128,
45.1744204123413,-2.6050599137291215,0.06739189697345527,-2.6724518107025768
```

Note: These are from different dates, but even when comparing similar timeframes, there are significant price differences that could be due to:

- Different data sources (KIS API vs Yahoo Finance)
- Potential stock splits or adjustments
- Data quality issues

# Backtest Result Comparison
## TSLA Example (from result files):

KIS Result:
```
총 거래: 9회
승률: 55.56% (5/9)
최종 자본: $1,043.34
총 손익: $-156.66
```

YFinance Result:
```
총 거래: 4회
승률: 50.00% (2/4)
최종 자본: $1,269.28
총 손익: $69.28
```

Difference: $225.94 (YFinance outperformed by 18.8%)

## Root Causes
### 1. KIS API Limitations
The KIS API appears to have limited historical data availability:

- Only provides ~1 month of minute/hourly data
- May have rate limits that prevent fetching deeper history
- The _fetch_overseas_minute_data function in fetcher.py shows complex pagination logic, suggesting API constraints

### 2. Data Source Reliability
- YFinance: Provides comprehensive historical data (1+ years)
- KIS: Limited to recent data, possibly due to API tier or endpoint limitations

### 3. Market Hours Alignment
The different timestamps suggest:

- KIS might be capturing Korean market hours or specific trading sessions
- YFinance captures US market hours (23:30 KST = 14:30 EST during winter)

## Recommendations
### For Accurate Backtesting:
1. Use YFinance for Historical Analysis

- Better data coverage (1+ years)
- More reliable for backtesting strategies
- Consistent timestamp alignment

2. Use KIS for Live Trading

- Real-time data from Korean broker
- Better for production trading
- Aligns with actual trading capabilities

3. Data Validation

- Always check data coverage before running backtests
- Verify timestamp alignment across all symbols
- Compare price ranges to ensure data quality

4. Hybrid Approach

- Develop and backtest strategies using YFinance data
- Validate with KIS data for recent periods
- Use KIS for live trading execution

## Technical Details
### File Locations:
- KIS Data: /data/kis/{symbol}/1h.csv
- YFinance Data: /data/yfinance/{symbol}/1h.csv
- KIS Results: kis_result.txt
- YFinance Results: yfinance_result.txt

### Data Fetchers:
- KIS: data_fetcher/fetcher.py (KisFetcher class)
- YFinance: data_fetcher/yfinance_fetcher.py (YFinanceFetcher class)

### Known Issues:
- KIS API has pagination complexity for historical data
- Some symbols missing in KIS data (e.g., TSLT, BTCL, NVDX)
- Timezone handling differs between sources