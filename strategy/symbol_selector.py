"""
종목선정 모듈
요구사항: 17:00~18:00 실행, 전일 포지션의 반대 포지션 우선 검토
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import TARGET_SYMBOLS, get_etf_by_original, get_original_symbols
from data.data_fetcher import DataFetcher
from strategy.indicators import TechnicalIndicators
from utils.logger import logger

class SymbolSelector:
    """종목선정 클래스"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.indicators = TechnicalIndicators()
    
    def select_symbols(
        self,
        previous_positions: Optional[Dict[str, str]] = None,
        max_symbols: int = 3
    ) -> List[Dict[str, any]]:
        """
        종목선정 - 원본 주식 코드를 분석하여 2x ETF LONG/SHORT 선택
        
        Args:
            previous_positions: 전일 포지션 정보 {etf_symbol: side} 형태 (예: {"TSLL": "LONG"})
            max_symbols: 최대 선택 종목 수
        
        Returns:
            우선순위화된 종목 리스트 [{"original": str, "symbol": str, "side": str, "score": float, "reason": str}, ...]
            - original: 원본 주식 코드 (예: "TSLA")
            - symbol: 실제 거래할 ETF 심볼 (예: "TSLL" 또는 "TSLZ")
            - side: 포지션 방향 ("LONG" or "SHORT")
        """
        candidates = []
        
        # 전일 포지션에서 원본 주식 추출
        previous_original_positions = {}
        if previous_positions:
            for etf_symbol, side in previous_positions.items():
                # ETF 심볼로부터 원본 주식 찾기
                for item in TARGET_SYMBOLS:
                    if item["LONG"] == etf_symbol or item["SHORT"] == etf_symbol:
                        original = item["ORIGINAL"]
                        previous_original_positions[original] = side
                        break
        
        # 1. 전일 포지션이 있었을 경우 반대 포지션 우선 검토
        if previous_original_positions:
            for original, previous_side in previous_original_positions.items():
                etf_info = get_etf_by_original(original)
                if not etf_info:
                    continue
                
                # 반대 포지션 결정
                opposite_side = "SHORT" if previous_side == "LONG" else "LONG"
                opposite_etf = etf_info["SHORT"] if opposite_side == "SHORT" else etf_info["LONG"]
                
                # 원본 주식 분석하여 반대 포지션 검토
                score, reason = self._evaluate_original_stock(original, opposite_side)
                if score > 0:
                    candidates.append({
                        "original": original,
                        "symbol": opposite_etf,
                        "side": opposite_side,
                        "score": score * 1.5,  # 반대 포지션 우선순위 가중치
                        "reason": f"반대 포지션 우선 검토: {reason}"
                    })
                    logger.info(f"{original} 반대 포지션({opposite_side} -> {opposite_etf}) 검토: 점수 {score:.2f}")
        
        # 2. 모든 원본 주식 검토
        for item in TARGET_SYMBOLS:
            original = item["ORIGINAL"]
            
            # 이미 반대 포지션으로 추가된 종목은 스킵
            if any(c["original"] == original for c in candidates):
                continue
            
            # 롱 포지션 검토 (원본 주식 분석)
            long_score, long_reason = self._evaluate_original_stock(original, "LONG")
            if long_score > 0:
                candidates.append({
                    "original": original,
                    "symbol": item["LONG"],
                    "side": "LONG",
                    "score": long_score,
                    "reason": long_reason
                })
            
            # 숏 포지션 검토 (원본 주식 분석)
            short_score, short_reason = self._evaluate_original_stock(original, "SHORT")
            if short_score > 0:
                candidates.append({
                    "original": original,
                    "symbol": item["SHORT"],
                    "side": "SHORT",
                    "score": short_score,
                    "reason": short_reason
                })
        
        # 3. 점수 기준으로 정렬
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # 4. 상위 N개 선택
        selected = candidates[:max_symbols]
        
        logger.info(f"종목선정 완료: {len(selected)}개 선택")
        for item in selected:
            logger.info(f"  - {item['original']} -> {item['symbol']} {item['side']}: 점수 {item['score']:.2f} ({item['reason']})")
        
        return selected
    
    def _evaluate_original_stock(self, original_symbol: str, side: str) -> tuple:
        """
        원본 주식 평가 - 원본 주식의 거래 상황을 분석하여 2x ETF LONG/SHORT 결정
        
        Args:
            original_symbol: 원본 주식 심볼 (예: "TSLA", "NVDA")
            side: 포지션 방향 ("LONG" or "SHORT")
        
        Returns:
            (점수, 이유) 튜플
        """
        try:
            # 원본 주식 데이터 수집 (분봉 데이터)
            data = self.data_fetcher.get_intraday_data(original_symbol, interval="5m")
            if data is None or len(data) < 50:
                return 0.0, "데이터 부족"
            
            # 기술적 지표 계산
            rsi = self.indicators.get_latest_rsi(data)
            macd = self.indicators.get_latest_macd(data)
            
            if rsi is None or macd is None:
                return 0.0, "지표 계산 실패"
            
            # 유동성 체크 (간단히 거래량 기준)
            avg_volume = data['volume'].tail(20).mean()
            if avg_volume < 1000000:  # 원본 주식은 더 높은 거래량 기준
                return 0.0, "유동성 부족"
            
            score = 0.0
            reasons = []
            
            # 롱 포지션 평가 (원본 주식이 상승 추세면 LONG ETF 선택)
            if side == "LONG":
                if rsi < 40 and macd.get("histogram", 0) > 0:
                    score += 0.5
                    reasons.append("RSI 낮음 + MACD 상승")
                if rsi < 30:
                    score += 0.3
                    reasons.append("RSI 과매도")
                if macd.get("histogram", 0) > 0.5:
                    score += 0.2
                    reasons.append("MACD 강한 상승")
                # 가격 추세 확인
                price_change = (data['close'].iloc[-1] - data['close'].iloc[-20]) / data['close'].iloc[-20] * 100
                if price_change > 2:
                    score += 0.2
                    reasons.append("단기 상승 추세")
            
            # 숏 포지션 평가 (원본 주식이 하락 추세면 SHORT ETF 선택)
            elif side == "SHORT":
                if rsi > 60 and macd.get("histogram", 0) < 0:
                    score += 0.5
                    reasons.append("RSI 높음 + MACD 하락")
                if rsi > 70:
                    score += 0.3
                    reasons.append("RSI 과매수")
                if macd.get("histogram", 0) < -0.5:
                    score += 0.2
                    reasons.append("MACD 강한 하락")
                # 가격 추세 확인
                price_change = (data['close'].iloc[-1] - data['close'].iloc[-20]) / data['close'].iloc[-20] * 100
                if price_change < -2:
                    score += 0.2
                    reasons.append("단기 하락 추세")
            
            reason = ", ".join(reasons) if reasons else "평가 완료"
            return score, reason
            
        except Exception as e:
            logger.error(f"{original_symbol} 평가 실패: {e}")
            return 0.0, f"오류: {str(e)}"

