# intelligent_router.py
"""
LLM-as-a-Judge Intelligent Router
LLM 기반 지능형 라우터

소형 모델이 질문의 복잡도를 먼저 판별한 후
적절한 모델로 라우팅하는 지능형 시스템
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import time
import asyncio

try:
    from .config import MODEL_CONFIGS, TaskComplexity, ModelProvider
except ImportError:
    from config import MODEL_CONFIGS, TaskComplexity, ModelProvider


class ComplexityLevel(Enum):
    """복잡도 레벨 (Complexity Level)"""
    TRIVIAL = 1      # 단순 사실 확인, 번역
    SIMPLE = 2       # 간단한 질문응답
    MODERATE = 3     # 중간 복잡도
    COMPLEX = 4      # 분석, 추론 필요
    EXPERT = 5       # 전문가 수준, 다단계 추론


@dataclass
class ComplexityAnalysis:
    """복잡도 분석 결과"""
    level: ComplexityLevel
    confidence: float
    reasoning: str
    recommended_model: str
    estimated_tokens: int
    requires_tools: bool = False
    requires_knowledge: bool = False
    analysis_time_ms: float = 0


@dataclass
class RoutingDecision:
    """라우팅 결정"""
    selected_model: str
    fallback_model: str
    complexity: ComplexityAnalysis
    strategy: str
    cost_estimate: float
    latency_estimate_ms: int
    decision_time_ms: float


class JudgeLLM:
    """Judge LLM - 복잡도 판별 전용 경량 모델
    
    작은 모델(GPT-3.5, Claude Haiku 등)을 사용하여
    빠르게 질문의 복잡도를 판별합니다.
    """
    
    SYSTEM_PROMPT = """You are a query complexity analyzer. Analyze the user's query and classify its complexity.

Output JSON format:
{
    "level": 1-5 (1=trivial, 2=simple, 3=moderate, 4=complex, 5=expert),
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "requires_tools": true/false,
    "requires_knowledge": true/false,
    "estimated_response_tokens": number
}

Classification criteria:
- Level 1 (TRIVIAL): Simple facts, translations, basic math
- Level 2 (SIMPLE): One-step Q&A, summaries, formatting
- Level 3 (MODERATE): Multi-step reasoning, explanations
- Level 4 (COMPLEX): Analysis, code generation, creative writing
- Level 5 (EXPERT): Multi-domain expertise, long-form content, research

Be concise. Output only valid JSON."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self._client = None
    
    def _get_client(self):
        """LLM 클라이언트 초기화"""
        if self._client is None:
            try:
                from langchain_openai import ChatOpenAI
                self._client = ChatOpenAI(
                    model=self.model,
                    temperature=0,
                    max_tokens=200
                )
            except Exception:
                self._client = None
        return self._client
    
    async def analyze(self, query: str) -> ComplexityAnalysis:
        """쿼리 복잡도 분석"""
        start_time = time.time()
        
        client = self._get_client()
        
        if client:
            try:
                from langchain_core.messages import SystemMessage, HumanMessage
                
                response = await client.ainvoke([
                    SystemMessage(content=self.SYSTEM_PROMPT),
                    HumanMessage(content=f"Analyze this query: {query}")
                ])
                
                result = json.loads(response.content)
                
                return ComplexityAnalysis(
                    level=ComplexityLevel(result["level"]),
                    confidence=result["confidence"],
                    reasoning=result["reasoning"],
                    recommended_model=self._get_recommended_model(result["level"]),
                    estimated_tokens=result.get("estimated_response_tokens", 500),
                    requires_tools=result.get("requires_tools", False),
                    requires_knowledge=result.get("requires_knowledge", False),
                    analysis_time_ms=(time.time() - start_time) * 1000
                )
            except Exception as e:
                print(f"⚠️ Judge LLM error: {e}")
        
        # 폴백: 휴리스틱 분석
        return self._heuristic_analyze(query, start_time)
    
    def _heuristic_analyze(self, query: str, start_time: float) -> ComplexityAnalysis:
        """휴리스틱 기반 복잡도 분석"""
        query_lower = query.lower()
        word_count = len(query.split())
        
        # 레벨 결정
        level = ComplexityLevel.MODERATE
        confidence = 0.7
        requires_tools = False
        requires_knowledge = False
        
        # TRIVIAL 패턴
        trivial_patterns = ["translate", "번역", "what is", "define", "뭐야", "언제"]
        if any(p in query_lower for p in trivial_patterns) and word_count < 15:
            level = ComplexityLevel.TRIVIAL
            confidence = 0.85
        
        # SIMPLE 패턴
        simple_patterns = ["summarize", "요약", "list", "how to", "어떻게"]
        if any(p in query_lower for p in simple_patterns):
            level = ComplexityLevel.SIMPLE
            confidence = 0.8
        
        # COMPLEX 패턴
        complex_patterns = [
            "analyze", "분석", "compare", "비교", "code", "코드",
            "implement", "구현", "design", "설계", "algorithm"
        ]
        if any(p in query_lower for p in complex_patterns):
            level = ComplexityLevel.COMPLEX
            confidence = 0.8
            requires_tools = "code" in query_lower or "코드" in query_lower
        
        # EXPERT 패턴
        expert_patterns = [
            "architecture", "아키텍처", "system design", "research",
            "optimize", "최적화", "strategic", "전략", "investment", "투자"
        ]
        if any(p in query_lower for p in expert_patterns):
            level = ComplexityLevel.EXPERT
            confidence = 0.75
            requires_knowledge = True
        
        # 길이 기반 보정
        if word_count > 100:
            if level.value < 4:
                level = ComplexityLevel.COMPLEX
        elif word_count > 50:
            if level.value < 3:
                level = ComplexityLevel.MODERATE
        
        return ComplexityAnalysis(
            level=level,
            confidence=confidence,
            reasoning=f"Heuristic analysis based on patterns and length ({word_count} words)",
            recommended_model=self._get_recommended_model(level.value),
            estimated_tokens=min(4000, word_count * 10 + 200),
            requires_tools=requires_tools,
            requires_knowledge=requires_knowledge,
            analysis_time_ms=(time.time() - start_time) * 1000
        )
    
    def _get_recommended_model(self, level: int) -> str:
        """복잡도에 따른 추천 모델"""
        model_map = {
            1: "gpt-4o-mini",      # TRIVIAL
            2: "gpt-4o-mini",      # SIMPLE
            3: "claude-3.5-sonnet", # MODERATE
            4: "claude-3.5-sonnet", # COMPLEX
            5: "claude-3-opus",     # EXPERT
        }
        return model_map.get(level, "claude-3.5-sonnet")


class IntelligentRouter:
    """지능형 라우터 (Intelligent Router)
    
    LLM-as-a-Judge 패턴을 사용하여 최적의 모델을 선택합니다.
    """
    
    def __init__(
        self,
        judge_model: str = "gpt-4o-mini",
        cost_weight: float = 0.3,
        quality_weight: float = 0.5,
        speed_weight: float = 0.2,
        use_judge_llm: bool = True
    ):
        """지능형 라우터 초기화
        
        Args:
            judge_model: 복잡도 판별용 모델
            cost_weight: 비용 가중치
            quality_weight: 품질 가중치
            speed_weight: 속도 가중치
            use_judge_llm: Judge LLM 사용 여부
        """
        self.judge = JudgeLLM(judge_model) if use_judge_llm else None
        self.cost_weight = cost_weight
        self.quality_weight = quality_weight
        self.speed_weight = speed_weight
        
        # 라우팅 이력
        self._history: List[RoutingDecision] = []
        
        # 모델별 성능 통계
        self._model_stats: Dict[str, Dict] = {}
    
    async def route(
        self,
        query: str,
        constraints: Dict[str, Any] = None
    ) -> RoutingDecision:
        """쿼리를 최적 모델로 라우팅
        
        Args:
            query: 쿼리 문자열
            constraints: 제약 조건 (max_cost, max_latency, preferred_models 등)
            
        Returns:
            RoutingDecision: 라우팅 결정
        """
        start_time = time.time()
        constraints = constraints or {}
        
        # 1. 복잡도 분석
        if self.judge:
            complexity = await self.judge.analyze(query)
        else:
            # use_judge_llm=False일 때 휴리스틱 분석기 사용
            heuristic_judge = JudgeLLM()
            complexity = heuristic_judge._heuristic_analyze(query, start_time)
        
        # 2. 후보 모델 필터링
        candidates = self._filter_candidates(complexity, constraints)
        
        # 3. 최적 모델 선택
        selected_model, fallback_model, strategy = self._select_optimal_model(
            candidates, complexity, constraints
        )
        
        # 4. 비용/레이턴시 추정
        model_config = MODEL_CONFIGS.get(selected_model)
        if model_config:
            cost_estimate = model_config.calculate_cost(
                complexity.estimated_tokens // 2,
                complexity.estimated_tokens // 2
            )
            latency_estimate = model_config.avg_latency_ms
        else:
            cost_estimate = 0.001
            latency_estimate = 1000
        
        decision = RoutingDecision(
            selected_model=selected_model,
            fallback_model=fallback_model,
            complexity=complexity,
            strategy=strategy,
            cost_estimate=cost_estimate,
            latency_estimate_ms=latency_estimate,
            decision_time_ms=(time.time() - start_time) * 1000
        )
        
        self._history.append(decision)
        
        return decision
    
    def _filter_candidates(
        self,
        complexity: ComplexityAnalysis,
        constraints: Dict[str, Any]
    ) -> List[str]:
        """후보 모델 필터링"""
        candidates = []
        
        max_cost = constraints.get("max_cost_per_query", float("inf"))
        max_latency = constraints.get("max_latency_ms", float("inf"))
        preferred_models = constraints.get("preferred_models", [])
        excluded_models = constraints.get("excluded_models", [])
        
        for model_key, config in MODEL_CONFIGS.items():
            # 제외 모델 필터
            if model_key in excluded_models:
                continue
            
            # 비용 필터
            estimated_cost = config.calculate_cost(500, 500)
            if estimated_cost > max_cost:
                continue
            
            # 레이턴시 필터
            if config.avg_latency_ms > max_latency:
                continue
            
            # 품질 필터 (복잡도에 따라)
            min_quality = {
                ComplexityLevel.TRIVIAL: 6.0,
                ComplexityLevel.SIMPLE: 7.0,
                ComplexityLevel.MODERATE: 7.5,
                ComplexityLevel.COMPLEX: 8.5,
                ComplexityLevel.EXPERT: 9.0,
            }.get(complexity.level, 7.0)
            
            if config.quality_score < min_quality:
                continue
            
            candidates.append(model_key)
        
        # 선호 모델 우선
        if preferred_models:
            preferred = [m for m in preferred_models if m in candidates]
            others = [m for m in candidates if m not in preferred_models]
            candidates = preferred + others
        
        return candidates if candidates else ["gpt-4o-mini"]
    
    def _select_optimal_model(
        self,
        candidates: List[str],
        complexity: ComplexityAnalysis,
        constraints: Dict[str, Any]
    ) -> Tuple[str, str, str]:
        """최적 모델 선택"""
        if not candidates:
            return "gpt-4o-mini", "gpt-3.5-turbo", "fallback"
        
        # 가중치 기반 점수 계산
        scores = []
        for model_key in candidates:
            config = MODEL_CONFIGS.get(model_key)
            if not config:
                continue
            
            # 정규화된 점수 (0-1)
            quality_score = config.quality_score / 10.0
            cost_score = 1.0 - min(1.0, config.input_cost_per_1k / 0.02)  # 비용 역수
            speed_score = 1.0 - min(1.0, config.avg_latency_ms / 5000)   # 레이턴시 역수
            
            # 복잡도에 따른 가중치 조정
            if complexity.level in [ComplexityLevel.EXPERT, ComplexityLevel.COMPLEX]:
                # 복잡한 작업: 품질 우선
                adjusted_quality_weight = self.quality_weight * 1.3
                adjusted_cost_weight = self.cost_weight * 0.7
            elif complexity.level in [ComplexityLevel.TRIVIAL, ComplexityLevel.SIMPLE]:
                # 간단한 작업: 비용/속도 우선
                adjusted_quality_weight = self.quality_weight * 0.7
                adjusted_cost_weight = self.cost_weight * 1.3
            else:
                adjusted_quality_weight = self.quality_weight
                adjusted_cost_weight = self.cost_weight
            
            total_score = (
                quality_score * adjusted_quality_weight +
                cost_score * adjusted_cost_weight +
                speed_score * self.speed_weight
            )
            
            scores.append((model_key, total_score))
        
        # 정렬
        scores.sort(key=lambda x: x[1], reverse=True)
        
        selected = scores[0][0] if scores else "gpt-4o-mini"
        fallback = scores[1][0] if len(scores) > 1 else "gpt-3.5-turbo"
        
        # 전략 결정
        strategy = "balanced"
        if self.quality_weight > 0.6:
            strategy = "quality_first"
        elif self.cost_weight > 0.5:
            strategy = "cost_optimized"
        elif self.speed_weight > 0.4:
            strategy = "speed_first"
        
        return selected, fallback, strategy
    
    def get_routing_history(self, limit: int = 100) -> List[RoutingDecision]:
        """라우팅 이력 조회"""
        return self._history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """라우팅 통계"""
        if not self._history:
            return {"message": "No routing history"}
        
        model_counts = {}
        complexity_counts = {}
        total_cost = 0
        total_latency = 0
        
        for decision in self._history:
            model_counts[decision.selected_model] = model_counts.get(decision.selected_model, 0) + 1
            complexity_counts[decision.complexity.level.name] = complexity_counts.get(decision.complexity.level.name, 0) + 1
            total_cost += decision.cost_estimate
            total_latency += decision.latency_estimate_ms
        
        return {
            "total_routings": len(self._history),
            "model_distribution": model_counts,
            "complexity_distribution": complexity_counts,
            "total_estimated_cost": total_cost,
            "avg_estimated_latency": total_latency / len(self._history) if self._history else 0
        }


# === 테스트 ===
async def test_intelligent_router():
    """지능형 라우터 테스트"""
    print("=" * 60)
    print("🧠 Intelligent Router Test (LLM-as-a-Judge)")
    print("=" * 60)
    
    router = IntelligentRouter(use_judge_llm=False)  # 휴리스틱 모드
    
    test_queries = [
        "Translate 'hello' to Korean",               # TRIVIAL
        "What is the capital of France?",            # SIMPLE
        "Explain how neural networks work",          # MODERATE
        "Write a Python algorithm for quicksort",    # COMPLEX
        "Design a microservices architecture for a banking system", # EXPERT
    ]
    
    for query in test_queries:
        decision = await router.route(query)
        
        print(f"\n📝 Query: {query[:50]}...")
        print(f"   Complexity: {decision.complexity.level.name} ({decision.complexity.confidence:.0%})")
        print(f"   Selected: {decision.selected_model}")
        print(f"   Fallback: {decision.fallback_model}")
        print(f"   Strategy: {decision.strategy}")
        print(f"   Est. Cost: ${decision.cost_estimate:.6f}")
        print(f"   Decision Time: {decision.decision_time_ms:.1f}ms")
    
    # 통계
    print("\n" + "=" * 60)
    print("📊 Routing Statistics")
    print("=" * 60)
    stats = router.get_statistics()
    print(f"   Model Distribution: {stats['model_distribution']}")
    print(f"   Complexity Distribution: {stats['complexity_distribution']}")
    
    print("\n✅ Intelligent Router Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_intelligent_router())
