# performance_monitor.py
"""
성능 모니터링
Performance Monitoring

비용, 레이턴시, 품질 메트릭을 추적하고 분석합니다.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

try:
    from .config import MODEL_CONFIGS, TaskComplexity
except ImportError:
    from config import MODEL_CONFIGS, TaskComplexity


@dataclass
class PerformanceMetric:
    """성능 메트릭 (Performance Metric)"""
    model: str
    latency_ms: float
    cost: float
    success: bool
    complexity: TaskComplexity
    timestamp: datetime = field(default_factory=datetime.now)
    cached: bool = False
    error: str = None


class PerformanceMonitor:
    """성능 모니터 (Performance Monitor)
    
    실시간으로 성능을 추적하고 분석합니다.
    """
    
    def __init__(self, alert_latency_ms: float = 5000, alert_error_rate: float = 0.1):
        """성능 모니터 초기화
        
        Args:
            alert_latency_ms: 레이턴시 알림 임계값 (밀리초)
            alert_error_rate: 에러율 알림 임계값
        """
        self._metrics: List[PerformanceMetric] = []
        self._alert_latency_ms = alert_latency_ms
        self._alert_error_rate = alert_error_rate
        
        # 모델별 통계
        self._model_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "latencies": [],
                "costs": [],
                "errors": 0,
                "cache_hits": 0
            }
        )
    
    def record(self, metric: PerformanceMetric):
        """메트릭 기록
        
        Args:
            metric: 성능 메트릭
        """
        self._metrics.append(metric)
        
        # 모델별 통계 업데이트
        stats = self._model_stats[metric.model]
        stats["count"] += 1
        stats["latencies"].append(metric.latency_ms)
        stats["costs"].append(metric.cost)
        
        if not metric.success:
            stats["errors"] += 1
        
        if metric.cached:
            stats["cache_hits"] += 1
        
        # 알림 확인
        self._check_alerts(metric)
    
    def _check_alerts(self, metric: PerformanceMetric):
        """알림 확인
        
        Args:
            metric: 성능 메트릭
        """
        # 레이턴시 알림
        if metric.latency_ms > self._alert_latency_ms:
            print(
                f"⚠️ High latency alert: {metric.model} "
                f"took {metric.latency_ms:.0f}ms "
                f"(threshold: {self._alert_latency_ms}ms)"
            )
        
        # 에러율 알림
        stats = self._model_stats[metric.model]
        if stats["count"] >= 10:  # 최소 10개 요청 후 체크
            error_rate = stats["errors"] / stats["count"]
            if error_rate > self._alert_error_rate:
                print(
                    f"🚨 Error rate alert: {metric.model} "
                    f"has {error_rate*100:.1f}% error rate"
                )
    
    def get_model_performance(self, model: str) -> Dict[str, Any]:
        """모델별 성능 분석
        
        Args:
            model: 모델 이름
            
        Returns:
            Dict: 모델 성능 정보
        """
        stats = self._model_stats[model]
        
        if stats["count"] == 0:
            return {"model": model, "message": "No data available"}
        
        latencies = stats["latencies"]
        costs = stats["costs"]
        
        return {
            "model": model,
            "total_requests": stats["count"],
            "error_rate": stats["errors"] / stats["count"],
            "cache_hit_rate": stats["cache_hits"] / stats["count"],
            "latency": {
                "mean": statistics.mean(latencies),
                "median": statistics.median(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies),
                "min": min(latencies),
                "max": max(latencies)
            },
            "cost": {
                "total": sum(costs),
                "mean": statistics.mean(costs),
                "median": statistics.median(costs)
            }
        }
    
    def get_complexity_analysis(self) -> Dict[str, Any]:
        """복잡도별 분석
        
        Returns:
            Dict: 복잡도별 성능 분석
        """
        complexity_stats = defaultdict(
            lambda: {"count": 0, "latencies": [], "costs": [], "models": []}
        )
        
        for metric in self._metrics:
            stats = complexity_stats[metric.complexity.value]
            stats["count"] += 1
            stats["latencies"].append(metric.latency_ms)
            stats["costs"].append(metric.cost)
            stats["models"].append(metric.model)
        
        result = {}
        for complexity, stats in complexity_stats.items():
            if stats["count"] > 0:
                result[complexity] = {
                    "count": stats["count"],
                    "avg_latency": statistics.mean(stats["latencies"]),
                    "avg_cost": statistics.mean(stats["costs"]),
                    "total_cost": sum(stats["costs"]),
                    "most_used_model": max(
                        set(stats["models"]),
                        key=stats["models"].count
                    )
                }
        
        return result
    
    def get_time_series_analysis(
        self,
        interval_minutes: int = 60,
        lookback_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """시계열 분석
        
        Args:
            interval_minutes: 집계 간격 (분)
            lookback_hours: 분석 기간 (시간)
            
        Returns:
            List[Dict]: 시계열 데이터
        """
        now = datetime.now()
        start_time = now - timedelta(hours=lookback_hours)
        
        # 시간 구간별 집계
        intervals = []
        current = start_time
        
        while current < now:
            interval_end = current + timedelta(minutes=interval_minutes)
            
            interval_metrics = [
                m for m in self._metrics
                if current <= m.timestamp < interval_end
            ]
            
            if interval_metrics:
                intervals.append({
                    "start": current.isoformat(),
                    "end": interval_end.isoformat(),
                    "request_count": len(interval_metrics),
                    "avg_latency": statistics.mean(m.latency_ms for m in interval_metrics),
                    "total_cost": sum(m.cost for m in interval_metrics),
                    "error_count": sum(1 for m in interval_metrics if not m.success),
                    "cache_hit_count": sum(1 for m in interval_metrics if m.cached)
                })
            
            current = interval_end
        
        return intervals
    
    def get_summary(self) -> Dict[str, Any]:
        """전체 요약
        
        Returns:
            Dict: 성능 요약
        """
        if not self._metrics:
            return {"message": "No metrics recorded yet"}
        
        all_latencies = [m.latency_ms for m in self._metrics]
        all_costs = [m.cost for m in self._metrics]
        
        return {
            "total_requests": len(self._metrics),
            "total_cost": sum(all_costs),
            "avg_cost_per_request": statistics.mean(all_costs),
            "latency": {
                "mean": statistics.mean(all_latencies),
                "median": statistics.median(all_latencies),
                "p95": sorted(all_latencies)[int(len(all_latencies) * 0.95)] if len(all_latencies) >= 20 else max(all_latencies)
            },
            "error_rate": sum(1 for m in self._metrics if not m.success) / len(self._metrics),
            "cache_hit_rate": sum(1 for m in self._metrics if m.cached) / len(self._metrics),
            "models_used": list(set(m.model for m in self._metrics)),
            "complexity_breakdown": self.get_complexity_analysis(),
            "model_performance": {
                model: self.get_model_performance(model)
                for model in self._model_stats.keys()
            }
        }
    
    def generate_report(self) -> str:
        """리포트 생성
        
        Returns:
            str: 마크다운 형식의 리포트
        """
        summary = self.get_summary()
        
        if "message" in summary:
            return "# Performance Report\n\nNo data available yet."
        
        report = """# 📊 Performance Report

## Overview
| Metric | Value |
|--------|-------|
| Total Requests | {total_requests} |
| Total Cost | ${total_cost:.4f} |
| Avg Cost/Request | ${avg_cost_per_request:.6f} |
| Mean Latency | {mean_latency:.0f}ms |
| Cache Hit Rate | {cache_hit_rate:.1%} |
| Error Rate | {error_rate:.1%} |

## Model Performance
""".format(
            total_requests=summary["total_requests"],
            total_cost=summary["total_cost"],
            avg_cost_per_request=summary["avg_cost_per_request"],
            mean_latency=summary["latency"]["mean"],
            cache_hit_rate=summary["cache_hit_rate"],
            error_rate=summary["error_rate"]
        )
        
        # 모델별 성능
        for model, perf in summary["model_performance"].items():
            if "message" not in perf:
                report += f"""
### {model}
- Requests: {perf['total_requests']}
- Avg Latency: {perf['latency']['mean']:.0f}ms
- Total Cost: ${perf['cost']['total']:.4f}
- Error Rate: {perf['error_rate']:.1%}
"""
        
        # 복잡도별 분석
        report += "\n## Complexity Analysis\n"
        for complexity, stats in summary["complexity_breakdown"].items():
            report += f"""
### {complexity.upper()}
- Requests: {stats['count']}
- Avg Latency: {stats['avg_latency']:.0f}ms
- Total Cost: ${stats['total_cost']:.4f}
- Most Used Model: {stats['most_used_model']}
"""
        
        return report
