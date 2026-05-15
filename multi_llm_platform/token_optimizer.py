# token_optimizer.py
"""
토큰 카운터 및 비용 추적기
Token Counter and Cost Tracker

토큰 사용량을 계산하고 비용을 추적합니다.
tiktoken을 사용하여 정확한 토큰 카운팅을 제공합니다.
"""

from typing import Dict, Any, Optional
from datetime import datetime, date
from dataclasses import dataclass, field
from collections import defaultdict

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

try:
    from .config import MODEL_CONFIGS, ModelConfig, Config
except ImportError:
    from config import MODEL_CONFIGS, ModelConfig, Config


@dataclass
class UsageRecord:
    """사용량 기록 (Usage Record)
    
    Attributes:
        model_name: 모델 이름
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        cost: 비용 (USD)
        latency_ms: 레이턴시 (밀리초)
        timestamp: 타임스탬프
        cached: 캐시 히트 여부
    """
    model_name: str
    input_tokens: int
    output_tokens: int
    cost: float
    latency_ms: int
    timestamp: datetime = field(default_factory=datetime.now)
    cached: bool = False


class TokenCounter:
    """토큰 카운터 (Token Counter)
    
    OpenAI의 tiktoken을 사용하여 정확한 토큰 수를 계산합니다.
    """
    
    def __init__(self):
        """토큰 카운터 초기화"""
        self._encoders: Dict[str, Any] = {}
    
    def _get_encoder(self, model_name: str):
        """모델별 인코더 반환
        
        Args:
            model_name: 모델 이름
            
        Returns:
            tiktoken.Encoding: 토큰 인코더
        """
        if not TIKTOKEN_AVAILABLE:
            return None
            
        if model_name not in self._encoders:
            try:
                # OpenAI 모델용 인코더
                if "gpt-4" in model_name or "gpt-3.5" in model_name:
                    self._encoders[model_name] = tiktoken.encoding_for_model(model_name)
                else:
                    # 다른 모델은 cl100k_base 사용 (근사값)
                    self._encoders[model_name] = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._encoders[model_name] = tiktoken.get_encoding("cl100k_base")
                
        return self._encoders[model_name]
    
    def count_tokens(self, text: str, model_name: str = "gpt-4") -> int:
        """텍스트의 토큰 수 계산
        
        Args:
            text: 토큰을 셀 텍스트
            model_name: 모델 이름
            
        Returns:
            int: 토큰 수
        """
        encoder = self._get_encoder(model_name)
        
        if encoder:
            return len(encoder.encode(text))
        else:
            # tiktoken이 없으면 근사값 사용 (4자당 1토큰)
            return len(text) // 4
    
    def estimate_cost(
        self,
        input_text: str,
        output_text: str,
        model_key: str
    ) -> Dict[str, Any]:
        """비용 추정
        
        Args:
            input_text: 입력 텍스트
            output_text: 출력 텍스트
            model_key: 모델 키
            
        Returns:
            Dict: 토큰 수와 비용 정보
        """
        config = MODEL_CONFIGS.get(model_key)
        
        if not config:
            return {"error": f"Unknown model: {model_key}"}
        
        input_tokens = self.count_tokens(input_text, config.model_name)
        output_tokens = self.count_tokens(output_text, config.model_name)
        cost = config.calculate_cost(input_tokens, output_tokens)
        
        return {
            "model": model_key,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost,
            "cost_formatted": f"${cost:.6f}"
        }


class CostTracker:
    """비용 추적기 (Cost Tracker)
    
    일별/월별 비용을 추적하고 예산 초과 시 알림을 제공합니다.
    """
    
    def __init__(self, daily_budget: float = None, alert_threshold: float = None):
        """비용 추적기 초기화
        
        Args:
            daily_budget: 일일 예산 (USD)
            alert_threshold: 알림 임계값 (USD)
        """
        self.daily_budget = daily_budget or Config.DAILY_BUDGET_USD
        self.alert_threshold = alert_threshold or Config.ALERT_THRESHOLD_USD
        
        self._usage_records: list = []
        self._daily_costs: Dict[date, float] = defaultdict(float)
        self._model_costs: Dict[str, float] = defaultdict(float)
        
        self.token_counter = TokenCounter()
    
    def record_usage(self, record: UsageRecord):
        """사용량 기록
        
        Args:
            record: 사용량 기록
        """
        self._usage_records.append(record)
        
        today = record.timestamp.date()
        self._daily_costs[today] += record.cost
        self._model_costs[record.model_name] += record.cost
        
        # 예산 알림 확인
        self._check_budget_alerts(today)
    
    def _check_budget_alerts(self, check_date: date):
        """예산 알림 확인
        
        Args:
            check_date: 확인할 날짜
        """
        daily_cost = self._daily_costs[check_date]
        
        if daily_cost >= self.daily_budget:
            print(f"🚨 BUDGET EXCEEDED! Daily cost: ${daily_cost:.4f}")
        elif daily_cost >= self.alert_threshold:
            print(f"⚠️ Budget Warning: ${daily_cost:.4f} / ${self.daily_budget:.2f}")
    
    def get_daily_cost(self, target_date: date = None) -> float:
        """일별 비용 조회
        
        Args:
            target_date: 조회할 날짜 (기본: 오늘)
            
        Returns:
            float: 일별 비용 (USD)
        """
        target_date = target_date or date.today()
        return self._daily_costs[target_date]
    
    def get_model_costs(self) -> Dict[str, float]:
        """모델별 비용 조회
        
        Returns:
            Dict: 모델별 비용
        """
        return dict(self._model_costs)
    
    def get_summary(self) -> Dict[str, Any]:
        """비용 요약
        
        Returns:
            Dict: 비용 요약 정보
        """
        total_cost = sum(self._daily_costs.values())
        total_records = len(self._usage_records)
        
        if total_records > 0:
            avg_cost = total_cost / total_records
            total_input_tokens = sum(r.input_tokens for r in self._usage_records)
            total_output_tokens = sum(r.output_tokens for r in self._usage_records)
            cached_count = sum(1 for r in self._usage_records if r.cached)
        else:
            avg_cost = 0
            total_input_tokens = 0
            total_output_tokens = 0
            cached_count = 0
        
        return {
            "total_cost": total_cost,
            "total_requests": total_records,
            "average_cost_per_request": avg_cost,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "cache_hit_rate": cached_count / total_records if total_records > 0 else 0,
            "daily_costs": dict(self._daily_costs),
            "model_costs": dict(self._model_costs),
            "budget_remaining": self.daily_budget - self.get_daily_cost()
        }
    
    def estimate_query_cost(
        self,
        input_text: str,
        model_key: str,
        expected_output_tokens: int = 500
    ) -> Dict[str, Any]:
        """쿼리 비용 사전 추정
        
        Args:
            input_text: 입력 텍스트
            model_key: 모델 키
            expected_output_tokens: 예상 출력 토큰 수
            
        Returns:
            Dict: 추정 비용 정보
        """
        config = MODEL_CONFIGS.get(model_key)
        
        if not config:
            return {"error": f"Unknown model: {model_key}"}
        
        input_tokens = self.token_counter.count_tokens(input_text, config.model_name)
        estimated_cost = config.calculate_cost(input_tokens, expected_output_tokens)
        
        return {
            "model": model_key,
            "input_tokens": input_tokens,
            "expected_output_tokens": expected_output_tokens,
            "estimated_cost": estimated_cost,
            "current_daily_spend": self.get_daily_cost(),
            "budget_remaining": self.daily_budget - self.get_daily_cost(),
            "within_budget": (self.get_daily_cost() + estimated_cost) <= self.daily_budget
        }
