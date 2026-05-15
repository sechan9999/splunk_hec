# __init__.py
"""
Multi-LLM Platform
==================

비용을 최적화하는 멀티 LLM 라우터 플랫폼입니다.

주요 기능:
1. 작업 복잡도 기반 모델 선택
2. 비용 최적화 라우팅
3. 응답 캐싱
4. 성능 모니터링

사용 예시:
    from multi_llm_platform import LLMRouter, RouteStrategy
    
    # 라우터 초기화
    router = LLMRouter(strategy=RouteStrategy.BALANCED)
    
    # 프롬프트에 대한 최적 모델 추천
    recommendation = router.get_routing_recommendation("코드를 작성해줘")
    
    # 쿼리 실행
    result = await router.route_and_execute("간단한 질문")
"""

from .config import (
    ModelProvider,
    TaskComplexity,
    ModelConfig,
    MODEL_CONFIGS,
    TASK_TO_MODEL_MAP,
    Config
)

from .token_optimizer import (
    TokenCounter,
    CostTracker,
    UsageRecord
)

from .cache_manager import (
    CacheBackend,
    MemoryCache,
    RedisCache,
    CacheManager
)

from .llm_router import (
    RouteStrategy,
    LLMRouter
)

from .performance_monitor import (
    PerformanceMetric,
    PerformanceMonitor
)

__all__ = [
    # Config
    "ModelProvider",
    "TaskComplexity",
    "ModelConfig",
    "MODEL_CONFIGS",
    "TASK_TO_MODEL_MAP",
    "Config",
    # Token Optimizer
    "TokenCounter",
    "CostTracker",
    "UsageRecord",
    # Cache
    "CacheBackend",
    "MemoryCache",
    "RedisCache",
    "CacheManager",
    # Router
    "RouteStrategy",
    "LLMRouter",
    # Monitor
    "PerformanceMetric",
    "PerformanceMonitor"
]

__version__ = "1.0.0"
