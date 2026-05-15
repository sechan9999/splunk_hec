# llm_router.py
"""
멀티 LLM 라우터
Multi-LLM Router

작업 복잡도에 따라 최적의 LLM을 선택하고
비용과 품질을 최적화합니다.
"""

import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

try:
    from .config import (
        MODEL_CONFIGS, ModelConfig, ModelProvider, TaskComplexity,
        TASK_TO_MODEL_MAP, Config
    )
    from .token_optimizer import CostTracker, UsageRecord
    from .cache_manager import CacheManager
except ImportError:
    from config import (
        MODEL_CONFIGS, ModelConfig, ModelProvider, TaskComplexity,
        TASK_TO_MODEL_MAP, Config
    )
    from token_optimizer import CostTracker, UsageRecord
    from cache_manager import CacheManager


class RouteStrategy(Enum):
    """라우팅 전략 (Routing Strategy)"""
    COST_OPTIMIZED = "cost_optimized"     # 비용 최적화
    QUALITY_FIRST = "quality_first"        # 품질 우선
    SPEED_FIRST = "speed_first"            # 속도 우선
    BALANCED = "balanced"                   # 균형


class LLMRouter:
    """멀티 LLM 라우터 (Multi-LLM Router)
    
    작업 특성에 따라 최적의 LLM을 선택합니다.
    """
    
    def __init__(
        self,
        strategy: RouteStrategy = RouteStrategy.BALANCED,
        use_cache: bool = True,
        use_redis: bool = False
    ):
        """LLM 라우터 초기화
        
        Args:
            strategy: 라우팅 전략
            use_cache: 캐시 사용 여부
            use_redis: Redis 캐시 사용 여부
        """
        self.strategy = strategy
        self.cost_tracker = CostTracker()
        self.cache_manager = CacheManager(use_redis=use_redis) if use_cache else None
        
        # 사용 가능한 모델 목록
        self._available_models = self._check_available_models()
    
    def _check_available_models(self) -> List[str]:
        """사용 가능한 모델 확인
        
        Returns:
            List[str]: 사용 가능한 모델 키 목록
        """
        available = []
        
        for model_key, config in MODEL_CONFIGS.items():
            if Config.is_provider_available(config.provider):
                available.append(model_key)
        
        if not available:
            print("⚠️ No API keys configured. Running in simulation mode.")
            # 시뮬레이션 모드: 모든 모델 사용 가능으로 간주
            available = list(MODEL_CONFIGS.keys())
        
        return available
    
    def analyze_task(self, prompt: str) -> TaskComplexity:
        """작업 복잡도 분석
        
        프롬프트를 분석하여 복잡도를 추정합니다.
        
        Args:
            prompt: 분석할 프롬프트
            
        Returns:
            TaskComplexity: 추정된 복잡도
        """
        prompt_lower = prompt.lower()
        token_count = len(prompt.split())
        
        # CRITICAL 키워드
        critical_keywords = [
            "결정", "판단", "의사결정", "critical", "decision",
            "중요한", "법적", "의료", "금융", "투자"
        ]
        if any(kw in prompt_lower for kw in critical_keywords):
            return TaskComplexity.CRITICAL
        
        # COMPLEX 키워드
        complex_keywords = [
            "코드", "프로그래밍", "알고리즘", "분석", "추론",
            "code", "programming", "algorithm", "analyze", "reason",
            "설계", "아키텍처", "최적화"
        ]
        if any(kw in prompt_lower for kw in complex_keywords):
            return TaskComplexity.COMPLEX
        
        # 토큰 수 기반 판단
        if token_count > 500:
            return TaskComplexity.COMPLEX
        elif token_count > 100:
            return TaskComplexity.MEDIUM
        
        # SIMPLE 키워드
        simple_keywords = [
            "뭐야", "무엇", "언제", "어디", "누가",
            "what", "when", "where", "who", "define",
            "번역", "translate", "요약", "summarize"
        ]
        if any(kw in prompt_lower for kw in simple_keywords):
            return TaskComplexity.SIMPLE
        
        return TaskComplexity.MEDIUM
    
    def select_model(
        self,
        prompt: str,
        complexity: TaskComplexity = None,
        strategy: RouteStrategy = None
    ) -> str:
        """최적의 모델 선택
        
        Args:
            prompt: 프롬프트
            complexity: 작업 복잡도 (자동 분석 시 None)
            strategy: 라우팅 전략 (None이면 기본 전략 사용)
            
        Returns:
            str: 선택된 모델 키
        """
        start_time = time.time()

        # 복잡도 분석
        if complexity is None:
            complexity = self.analyze_task(prompt)

        strategy = strategy or self.strategy
        
        # 해당 복잡도에 적합한 후보 모델 목록
        candidates = TASK_TO_MODEL_MAP.get(complexity, ["gpt-4o-mini"])
        
        # 사용 가능한 모델만 필터링
        available_candidates = [
            m for m in candidates if m in self._available_models
        ]
        
        if not available_candidates:
            # 폴백: 사용 가능한 모델 중 아무거나
            available_candidates = self._available_models or ["gpt-4o-mini"]
        
        # 전략에 따른 정렬
        if strategy == RouteStrategy.COST_OPTIMIZED:
            # 비용 최적화: 가장 저렴한 모델
            sorted_models = sorted(
                available_candidates,
                key=lambda m: MODEL_CONFIGS[m].input_cost_per_1k
            )
        elif strategy == RouteStrategy.QUALITY_FIRST:
            # 품질 우선: 품질 점수 높은 순
            sorted_models = sorted(
                available_candidates,
                key=lambda m: MODEL_CONFIGS[m].quality_score,
                reverse=True
            )
        elif strategy == RouteStrategy.SPEED_FIRST:
            # 속도 우선: 레이턴시 낮은 순
            sorted_models = sorted(
                available_candidates,
                key=lambda m: MODEL_CONFIGS[m].avg_latency_ms
            )
        else:  # BALANCED
            # 균형: 복합 점수
            def score(m):
                config = MODEL_CONFIGS[m]
                # 품질과 비용의 균형 (비용 역가중)
                cost_score = 1 / (config.input_cost_per_1k + 0.001)
                quality_score = config.quality_score
                speed_score = 1 / (config.avg_latency_ms + 1)
                return quality_score * 0.5 + cost_score * 0.3 + speed_score * 0.2
            
            sorted_models = sorted(
                available_candidates,
                key=score,
                reverse=True
            )
        
        selected = sorted_models[0] if sorted_models else "gpt-4o-mini"

        try:
            from splunk_telemetry import get_telemetry
            fallback = sorted_models[1] if len(sorted_models) > 1 else ""
            get_telemetry().emit_router_decision(
                complexity=complexity.value,
                confidence=0.85,
                selected_model=selected,
                fallback_model=fallback,
                strategy=(strategy or self.strategy).value,
                decision_time_ms=(time.time() - start_time) * 1000
            )
        except Exception:
            pass

        return selected
    
    def get_model_info(self, model_key: str) -> Dict[str, Any]:
        """모델 정보 조회
        
        Args:
            model_key: 모델 키
            
        Returns:
            Dict: 모델 정보
        """
        config = MODEL_CONFIGS.get(model_key)
        
        if not config:
            return {"error": f"Unknown model: {model_key}"}
        
        return {
            "model_key": model_key,
            "model_name": config.model_name,
            "provider": config.provider.value,
            "input_cost_per_1k": config.input_cost_per_1k,
            "output_cost_per_1k": config.output_cost_per_1k,
            "max_tokens": config.max_tokens,
            "avg_latency_ms": config.avg_latency_ms,
            "quality_score": config.quality_score,
            "available": model_key in self._available_models
        }
    
    async def route_and_execute(
        self,
        prompt: str,
        temperature: float = 0.0,
        complexity: TaskComplexity = None,
        force_model: str = None
    ) -> Dict[str, Any]:
        """라우팅 및 실행
        
        모델을 선택하고 쿼리를 실행합니다.
        
        Args:
            prompt: 프롬프트
            temperature: 온도 설정
            complexity: 작업 복잡도
            force_model: 강제 지정 모델
            
        Returns:
            Dict: 실행 결과
        """
        start_time = time.time()
        
        # 모델 선택
        if force_model and force_model in self._available_models:
            selected_model = force_model
        else:
            selected_model = self.select_model(prompt, complexity)
        
        model_config = MODEL_CONFIGS[selected_model]
        
        # 캐시 확인
        if self.cache_manager:
            cached = self.cache_manager.get(prompt, selected_model, temperature)
            if cached:
                latency = (time.time() - start_time) * 1000

                self.cost_tracker.record_usage(UsageRecord(
                    model_name=selected_model,
                    input_tokens=0,
                    output_tokens=0,
                    cost=0.0,
                    latency_ms=int(latency),
                    cached=True
                ))

                try:
                    from splunk_telemetry import get_telemetry
                    get_telemetry().emit_cache_hit(
                        model=selected_model,
                        saved_latency_ms=latency
                    )
                except Exception:
                    pass

                return {
                    "response": cached["response"],
                    "model": selected_model,
                    "cached": True,
                    "latency_ms": latency,
                    "cost": 0.0
                }

        # 캐시 미스 기록
        try:
            from splunk_telemetry import get_telemetry
            get_telemetry().emit_cache_miss(model=selected_model)
        except Exception:
            pass

        # 실제 LLM 호출 (시뮬레이션)
        response, input_tokens, output_tokens = await self._call_llm(
            prompt, selected_model, temperature
        )

        latency = (time.time() - start_time) * 1000
        cost = model_config.calculate_cost(input_tokens, output_tokens)

        # 사용량 기록
        self.cost_tracker.record_usage(UsageRecord(
            model_name=selected_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            latency_ms=int(latency),
            cached=False
        ))

        try:
            from splunk_telemetry import get_telemetry
            complexity_val = (complexity or self.analyze_task(prompt)).value
            get_telemetry().emit_llm_call(
                model=selected_model,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency,
                success=True,
                cached=False,
                complexity=complexity_val
            )
        except Exception:
            pass
        
        # 캐시 저장
        if self.cache_manager and temperature == 0:
            self.cache_manager.set(
                prompt, selected_model,
                {"response": response},
                temperature
            )
        
        return {
            "response": response,
            "model": selected_model,
            "cached": False,
            "latency_ms": latency,
            "cost": cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
    
    async def _call_llm(
        self,
        prompt: str,
        model_key: str,
        temperature: float
    ) -> tuple:
        """LLM 호출 (실제 구현 또는 시뮬레이션)
        
        Args:
            prompt: 프롬프트
            model_key: 모델 키
            temperature: 온도 설정
            
        Returns:
            tuple: (응답, 입력 토큰 수, 출력 토큰 수)
        """
        config = MODEL_CONFIGS[model_key]
        
        try:
            # 실제 LLM 호출 시도
            if config.provider == ModelProvider.OPENAI:
                return await self._call_openai(prompt, config, temperature)
            elif config.provider == ModelProvider.ANTHROPIC:
                return await self._call_anthropic(prompt, config, temperature)
            elif config.provider == ModelProvider.GOOGLE:
                return await self._call_google(prompt, config, temperature)
        except ImportError:
            pass
        except Exception as e:
            print(f"⚠️ LLM call failed: {e}")
        
        # 시뮬레이션 응답
        return self._simulate_response(prompt, model_key)
    
    async def _call_openai(self, prompt: str, config: ModelConfig, temperature: float) -> tuple:
        """OpenAI API 호출"""
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        
        llm = ChatOpenAI(
            model=config.model_name,
            temperature=temperature
        )
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # 토큰 수 추정
        input_tokens = len(prompt) // 4
        output_tokens = len(response.content) // 4
        
        return response.content, input_tokens, output_tokens
    
    async def _call_anthropic(self, prompt: str, config: ModelConfig, temperature: float) -> tuple:
        """Anthropic API 호출"""
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage
        
        llm = ChatAnthropic(
            model=config.model_name,
            temperature=temperature
        )
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        input_tokens = len(prompt) // 4
        output_tokens = len(response.content) // 4
        
        return response.content, input_tokens, output_tokens
    
    async def _call_google(self, prompt: str, config: ModelConfig, temperature: float) -> tuple:
        """Google API 호출"""
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        
        llm = ChatGoogleGenerativeAI(
            model=config.model_name,
            temperature=temperature
        )
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        input_tokens = len(prompt) // 4
        output_tokens = len(response.content) // 4
        
        return response.content, input_tokens, output_tokens
    
    def _simulate_response(self, prompt: str, model_key: str) -> tuple:
        """시뮬레이션 응답 생성"""
        config = MODEL_CONFIGS[model_key]
        
        # 시뮬레이션 지연
        import time
        time.sleep(config.avg_latency_ms / 1000 * 0.1)  # 10% 지연
        
        response = (
            f"[Simulated response from {model_key}]\n"
            f"This is a simulated response to your prompt.\n"
            f"Model: {config.model_name}\n"
            f"Provider: {config.provider.value}\n"
            f"Quality Score: {config.quality_score}"
        )
        
        input_tokens = len(prompt) // 4
        output_tokens = len(response) // 4
        
        return response, input_tokens, output_tokens
    
    def get_routing_recommendation(self, prompt: str) -> Dict[str, Any]:
        """라우팅 추천
        
        프롬프트에 대한 최적 모델 추천을 제공합니다.
        
        Args:
            prompt: 프롬프트
            
        Returns:
            Dict: 추천 정보
        """
        complexity = self.analyze_task(prompt)
        
        recommendations = {}
        for strategy in RouteStrategy:
            model = self.select_model(prompt, complexity, strategy)
            recommendations[strategy.value] = {
                "model": model,
                "info": self.get_model_info(model)
            }
        
        return {
            "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
            "detected_complexity": complexity.value,
            "recommendations": recommendations,
            "default_selection": self.select_model(prompt, complexity)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """통합 통계 조회
        
        Returns:
            Dict: 비용 및 캐시 통계
        """
        stats = {
            "cost": self.cost_tracker.get_summary(),
            "strategy": self.strategy.value,
            "available_models": self._available_models
        }
        
        if self.cache_manager:
            stats["cache"] = self.cache_manager.get_stats()
        
        return stats
