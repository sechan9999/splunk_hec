# main.py
"""
멀티 LLM 플랫폼 실행
Multi-LLM Platform Execution

비용을 최적화하는 멀티 LLM 라우터를 실행합니다.
"""

import argparse
import asyncio

from config import MODEL_CONFIGS, TaskComplexity
from llm_router import LLMRouter, RouteStrategy
from performance_monitor import PerformanceMonitor, PerformanceMetric


async def run_demo():
    """데모 실행"""
    print("""
💰 Multi-LLM Platform - Smart Cost Optimization
================================================

Features:
✓ Task Complexity Analysis
✓ Cost-Optimized Routing
✓ Response Caching
✓ Performance Monitoring
""")

    # 라우터 초기화
    router = LLMRouter(
        strategy=RouteStrategy.BALANCED,
        use_cache=True,
        use_redis=False
    )
    
    # 성능 모니터 초기화
    monitor = PerformanceMonitor()
    
    # 테스트 프롬프트
    test_prompts = [
        ("안녕하세요, 오늘 날씨는 어때요?", TaskComplexity.SIMPLE),
        ("파이썬으로 퀵소트 알고리즘을 구현해주세요.", TaskComplexity.COMPLEX),
        ("이 데이터를 분석하고 인사이트를 도출해주세요.", TaskComplexity.MEDIUM),
        ("회사의 5년 투자 전략을 수립해주세요.", TaskComplexity.CRITICAL),
    ]
    
    print("\n📊 Testing with different complexity levels...\n")
    
    for prompt, expected_complexity in test_prompts:
        print(f"{'='*60}")
        print(f"Prompt: {prompt[:50]}...")
        
        # 라우팅 추천 확인
        recommendation = router.get_routing_recommendation(prompt)
        detected = recommendation["detected_complexity"]
        selected_model = recommendation["default_selection"]
        
        print(f"Detected Complexity: {detected}")
        print(f"Selected Model: {selected_model}")
        
        # 실행
        result = await router.route_and_execute(prompt)
        
        print(f"Response (preview): {result['response'][:100]}...")
        print(f"Latency: {result['latency_ms']:.0f}ms")
        print(f"Cost: ${result['cost']:.6f}")
        print(f"Cached: {result['cached']}")
        
        # 성능 기록
        monitor.record(PerformanceMetric(
            model=result["model"],
            latency_ms=result["latency_ms"],
            cost=result["cost"],
            success=True,
            complexity=TaskComplexity(detected),
            cached=result.get("cached", False)
        ))
        
        print()
    
    # 캐시 테스트 (동일 쿼리 재실행)
    print(f"{'='*60}")
    print("Testing cache hit (repeating first query)...")
    result = await router.route_and_execute(test_prompts[0][0])
    print(f"Cached: {result['cached']}")
    print(f"Latency: {result['latency_ms']:.0f}ms")
    print(f"Cost: ${result['cost']:.6f}")
    print()
    
    # 통계 출력
    print(f"{'='*60}")
    print("📈 Statistics")
    print(f"{'='*60}\n")
    
    stats = router.get_stats()
    
    print("Cost Summary:")
    print(f"  Total Cost: ${stats['cost']['total_cost']:.6f}")
    print(f"  Total Requests: {stats['cost']['total_requests']}")
    print(f"  Avg Cost/Request: ${stats['cost']['average_cost_per_request']:.6f}")
    
    if "cache" in stats:
        print(f"\nCache Stats:")
        print(f"  Hit Rate: {stats['cache'].get('hit_rate_percent', 'N/A')}")
        print(f"  Hits: {stats['cache'].get('hits', 0)}")
        print(f"  Misses: {stats['cache'].get('misses', 0)}")
    
    print("\n" + "="*60)
    print("📊 Performance Report")
    print("="*60)
    print(monitor.generate_report())


def show_model_info():
    """모델 정보 표시"""
    print("""
📋 Available Models
===================
""")
    
    for model_key, config in MODEL_CONFIGS.items():
        print(f"""
{model_key}:
  Provider: {config.provider.value}
  Model Name: {config.model_name}
  Input Cost: ${config.input_cost_per_1k}/1K tokens
  Output Cost: ${config.output_cost_per_1k}/1K tokens
  Max Tokens: {config.max_tokens}
  Avg Latency: {config.avg_latency_ms}ms
  Quality Score: {config.quality_score}/10
""")


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description="Multi-LLM Platform - Smart Cost Optimization"
    )
    parser.add_argument(
        "--models",
        action="store_true",
        help="Show available models and pricing"
    )
    parser.add_argument(
        "--strategy",
        choices=["cost", "quality", "speed", "balanced"],
        default="balanced",
        help="Routing strategy"
    )
    
    args = parser.parse_args()
    
    if args.models:
        show_model_info()
    else:
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
