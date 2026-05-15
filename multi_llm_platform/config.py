# config.py
"""
설정 및 비용 구조
Configuration and Cost Structure

각 LLM 모델의 비용, 레이턴시, 품질 정보를 관리합니다.
"""

import os
from dataclasses import dataclass
from typing import Dict, List
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class ModelProvider(Enum):
    """LLM 프로바이더 (LLM Providers)"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class TaskComplexity(Enum):
    """작업 복잡도 레벨 (Task Complexity Levels)
    
    - SIMPLE: 간단한 질문, 분류
    - MEDIUM: 요약, 분석
    - COMPLEX: 추론, 코드 생성
    - CRITICAL: 의사결정, 중요 작업
    """
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CRITICAL = "critical"


@dataclass
class ModelConfig:
    """모델 설정 및 비용 정보
    
    Attributes:
        provider: LLM 프로바이더
        model_name: 모델 이름
        input_cost_per_1k: 입력 토큰 1K당 비용 (USD)
        output_cost_per_1k: 출력 토큰 1K당 비용 (USD)
        max_tokens: 최대 토큰 수
        avg_latency_ms: 평균 응답 시간 (밀리초)
        quality_score: 품질 점수 (1-10)
    """
    provider: ModelProvider
    model_name: str
    input_cost_per_1k: float
    output_cost_per_1k: float
    max_tokens: int
    avg_latency_ms: int
    quality_score: float

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """총 비용 계산
        
        Args:
            input_tokens: 입력 토큰 수
            output_tokens: 출력 토큰 수
            
        Returns:
            float: 총 비용 (USD)
        """
        input_cost = (input_tokens / 1000) * self.input_cost_per_1k
        output_cost = (output_tokens / 1000) * self.output_cost_per_1k
        return input_cost + output_cost


# 실제 가격 정보 (2025년 기준)
MODEL_CONFIGS: Dict[str, ModelConfig] = {
    # OpenAI 모델
    "gpt-4-turbo": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_name="gpt-4-turbo-preview",
        input_cost_per_1k=0.01,
        output_cost_per_1k=0.03,
        max_tokens=4096,
        avg_latency_ms=3000,
        quality_score=9.5
    ),
    "gpt-4o": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_name="gpt-4o",
        input_cost_per_1k=0.005,
        output_cost_per_1k=0.015,
        max_tokens=4096,
        avg_latency_ms=2000,
        quality_score=9.3
    ),
    "gpt-4o-mini": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_name="gpt-4o-mini",
        input_cost_per_1k=0.00015,
        output_cost_per_1k=0.0006,
        max_tokens=4096,
        avg_latency_ms=1000,
        quality_score=8.0
    ),
    "gpt-3.5-turbo": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_name="gpt-3.5-turbo",
        input_cost_per_1k=0.0005,
        output_cost_per_1k=0.0015,
        max_tokens=4096,
        avg_latency_ms=800,
        quality_score=7.5
    ),
    
    # Anthropic 모델
    "claude-3-opus": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_name="claude-3-opus-20240229",
        input_cost_per_1k=0.015,
        output_cost_per_1k=0.075,
        max_tokens=4096,
        avg_latency_ms=3500,
        quality_score=9.8
    ),
    "claude-3-sonnet": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_name="claude-3-sonnet-20240229",
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        max_tokens=4096,
        avg_latency_ms=2000,
        quality_score=8.5
    ),
    "claude-3-haiku": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_name="claude-3-haiku-20240307",
        input_cost_per_1k=0.00025,
        output_cost_per_1k=0.00125,
        max_tokens=4096,
        avg_latency_ms=500,
        quality_score=7.0
    ),
    "claude-3.5-sonnet": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_name="claude-3-5-sonnet-20241022",
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        max_tokens=4096,
        avg_latency_ms=1500,
        quality_score=9.2
    ),
    
    # Google 모델
    "gemini-pro": ModelConfig(
        provider=ModelProvider.GOOGLE,
        model_name="gemini-pro",
        input_cost_per_1k=0.00025,
        output_cost_per_1k=0.0005,
        max_tokens=2048,
        avg_latency_ms=1200,
        quality_score=8.0
    ),
    "gemini-2.0-flash": ModelConfig(
        provider=ModelProvider.GOOGLE,
        model_name="gemini-2.0-flash-exp",
        input_cost_per_1k=0.0,  # Free tier
        output_cost_per_1k=0.0,
        max_tokens=8192,
        avg_latency_ms=800,
        quality_score=8.5
    ),
}


# 태스크별 추천 모델 매핑
TASK_TO_MODEL_MAP: Dict[TaskComplexity, List[str]] = {
    TaskComplexity.SIMPLE: [
        "gpt-4o-mini", "claude-3-haiku", "gemini-2.0-flash", "gpt-3.5-turbo"
    ],
    TaskComplexity.MEDIUM: [
        "claude-3.5-sonnet", "gpt-4o", "claude-3-sonnet", "gemini-pro"
    ],
    TaskComplexity.COMPLEX: [
        "gpt-4-turbo", "claude-3.5-sonnet", "gpt-4o"
    ],
    TaskComplexity.CRITICAL: [
        "claude-3-opus", "gpt-4-turbo", "claude-3.5-sonnet"
    ],
}


class Config:
    """전역 설정 (Global Configuration)"""
    
    # API Keys (환경변수에서 로드)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    
    # 캐시 설정
    CACHE_ENABLED = True
    CACHE_TTL = 3600  # 1시간
    
    # Redis 설정
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
    
    # 성능 설정
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30
    
    # 비용 제한
    DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", 10.0))
    ALERT_THRESHOLD_USD = float(os.getenv("ALERT_THRESHOLD_USD", 8.0))
    
    @classmethod
    def get_api_key(cls, provider: ModelProvider) -> str:
        """프로바이더별 API 키 반환
        
        Args:
            provider: LLM 프로바이더
            
        Returns:
            str: API 키
        """
        key_map = {
            ModelProvider.OPENAI: cls.OPENAI_API_KEY,
            ModelProvider.ANTHROPIC: cls.ANTHROPIC_API_KEY,
            ModelProvider.GOOGLE: cls.GOOGLE_API_KEY,
        }
        return key_map.get(provider, "")
    
    @classmethod
    def is_provider_available(cls, provider: ModelProvider) -> bool:
        """프로바이더 사용 가능 여부 확인
        
        Args:
            provider: LLM 프로바이더
            
        Returns:
            bool: 사용 가능하면 True
        """
        return bool(cls.get_api_key(provider))
