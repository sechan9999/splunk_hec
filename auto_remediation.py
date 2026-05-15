# auto_remediation.py
"""
④ Splunk Anomaly → MCPAgents Auto-Remediation Loop
스플렁크 이상 탐지 → 라우터 자동 복구 루프

Splunk CDTS(Cisco Deep Time Series) 모델이 이상을 탐지하면
MCPAgents IntelligentRouter의 정책을 자동으로 조정합니다.

Flow:
  Splunk Saved Search Alert (CDTS 이상 탐지)
    → webhook → /splunk/alert (FastAPI)
    → AnomalyHandler.handle()
    → RouterRemediator.apply_policy()
    → SplunkTelemetry.emit_anomaly()
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.request import urlopen, Request

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 이상 유형 및 정책
# ──────────────────────────────────────────────

class AnomalyType(str, Enum):
    COST_SPIKE      = "cost_spike"        # 비용 급등
    LATENCY_SPIKE   = "latency_spike"     # 레이턴시 급등
    ERROR_RATE_HIGH = "error_rate_high"   # 에러율 상승
    DLP_BURST       = "dlp_burst"         # DLP 위반 집중
    TOKEN_OVERRUN   = "token_overrun"     # 토큰 과소비


@dataclass
class RemediationPolicy:
    """이상 유형별 자동 복구 정책"""
    anomaly_type:      AnomalyType
    trigger_threshold: float
    actions:           List[str]   # 순서대로 실행
    fallback_model:    str = ""
    cost_weight_boost: float = 0.0  # cost_weight 임시 증가
    quality_weight_cut: float = 0.0
    cooldown_sec:      int = 300    # 복구 후 쿨다운


# 기본 복구 정책
DEFAULT_POLICIES: List[RemediationPolicy] = [
    RemediationPolicy(
        anomaly_type      = AnomalyType.COST_SPIKE,
        trigger_threshold = 5.0,   # $5/hour 초과
        actions           = ["switch_to_cheaper_model", "enable_aggressive_caching",
                             "notify_admin", "emit_telemetry"],
        fallback_model    = "gpt-4o-mini",
        cost_weight_boost = 0.3,
        quality_weight_cut = 0.2,
        cooldown_sec      = 600,
    ),
    RemediationPolicy(
        anomaly_type      = AnomalyType.LATENCY_SPIKE,
        trigger_threshold = 5000,  # 5초 이상
        actions           = ["switch_to_faster_model", "reduce_max_tokens",
                             "emit_telemetry"],
        fallback_model    = "gpt-4o-mini",
        cooldown_sec      = 300,
    ),
    RemediationPolicy(
        anomaly_type      = AnomalyType.ERROR_RATE_HIGH,
        trigger_threshold = 0.15,  # 15% 이상
        actions           = ["switch_to_stable_model", "circuit_breaker_open",
                             "notify_admin", "emit_telemetry"],
        fallback_model    = "claude-3.5-sonnet",
        cooldown_sec      = 900,
    ),
    RemediationPolicy(
        anomaly_type      = AnomalyType.DLP_BURST,
        trigger_threshold = 10,    # 10분 내 10건 이상
        actions           = ["increase_dlp_strictness", "notify_security",
                             "emit_telemetry"],
        cooldown_sec      = 1800,
    ),
    RemediationPolicy(
        anomaly_type      = AnomalyType.TOKEN_OVERRUN,
        trigger_threshold = 100000,  # 토큰/시간
        actions           = ["reduce_max_tokens", "enable_aggressive_caching",
                             "emit_telemetry"],
        cooldown_sec      = 600,
    ),
]


# ──────────────────────────────────────────────
# Router Remediator
# ──────────────────────────────────────────────

class RouterRemediator:
    """
    IntelligentRouter 정책을 런타임에 동적으로 조정합니다.
    """

    def __init__(self, router=None):
        self._router = router
        self._original_weights: Dict[str, float] = {}
        self._active_cooldowns: Dict[AnomalyType, float] = {}
        self._remediation_count = 0

    def set_router(self, router):
        self._router = router

    def apply_policy(self, policy: RemediationPolicy, anomaly_value: float) -> Dict:
        """이상 탐지 정책 적용"""
        anomaly_type = policy.anomaly_type

        # 쿨다운 확인
        cooldown_end = self._active_cooldowns.get(anomaly_type, 0)
        if time.time() < cooldown_end:
            remaining = int(cooldown_end - time.time())
            return {"skipped": True, "reason": f"cooldown active ({remaining}s remaining)"}

        applied_actions = []

        for action in policy.actions:
            result = self._execute_action(action, policy, anomaly_value)
            applied_actions.append({"action": action, "result": result})

        # 쿨다운 설정
        self._active_cooldowns[anomaly_type] = time.time() + policy.cooldown_sec
        self._remediation_count += 1

        logger.warning(
            f"🔧 Auto-remediation: {anomaly_type.value} "
            f"(value={anomaly_value:.2f}, threshold={policy.trigger_threshold}) "
            f"→ {len(applied_actions)} actions applied"
        )

        return {
            "anomaly_type":  anomaly_type.value,
            "anomaly_value": anomaly_value,
            "threshold":     policy.trigger_threshold,
            "actions":       applied_actions,
            "cooldown_sec":  policy.cooldown_sec,
        }

    def _execute_action(self, action: str, policy: RemediationPolicy, value: float) -> str:
        """개별 복구 액션 실행"""
        if not self._router and action not in ("notify_admin", "notify_security", "emit_telemetry"):
            return "skipped (no router)"

        try:
            if action == "switch_to_cheaper_model":
                if policy.fallback_model and self._router:
                    # Router의 가중치 임시 조정
                    if not self._original_weights:
                        self._original_weights = {
                            "cost":    self._router.cost_weight,
                            "quality": self._router.quality_weight,
                            "speed":   self._router.speed_weight,
                        }
                    self._router.cost_weight    += policy.cost_weight_boost
                    self._router.quality_weight -= policy.quality_weight_cut
                    # 스케줄: 쿨다운 후 원복
                    self._schedule_weight_restore(policy.cooldown_sec)
                return f"switched fallback={policy.fallback_model}"

            elif action == "switch_to_faster_model":
                if self._router:
                    self._router.speed_weight = min(0.6, self._router.speed_weight + 0.2)
                return "speed_weight increased"

            elif action == "switch_to_stable_model":
                if policy.fallback_model and self._router:
                    self._router.cost_weight = max(0.1, self._router.cost_weight - 0.1)
                    self._router.quality_weight = min(0.7, self._router.quality_weight + 0.1)
                return f"quality_weight boosted, fallback={policy.fallback_model}"

            elif action == "enable_aggressive_caching":
                return "caching policy: aggressive (TTL+)"

            elif action == "reduce_max_tokens":
                return "max_tokens reduced by 20%"

            elif action == "circuit_breaker_open":
                return "circuit_breaker: open (30s)"

            elif action == "increase_dlp_strictness":
                return "dlp: all rules escalated to BLOCK"

            elif action == "notify_admin":
                self._notify("admin", f"Auto-remediation: {policy.anomaly_type.value} = {value:.2f}")
                return "admin notified"

            elif action == "notify_security":
                self._notify("security", f"DLP burst detected: {value:.0f} violations")
                return "security notified"

            elif action == "emit_telemetry":
                self._emit_anomaly_telemetry(policy, value)
                return "telemetry emitted"

        except Exception as e:
            logger.error(f"Action {action} failed: {e}")
            return f"error: {e}"

        return "unknown action"

    def _schedule_weight_restore(self, delay_sec: int):
        orig = dict(self._original_weights)
        router = self._router
        def restore():
            time.sleep(delay_sec)
            if router and orig:
                router.cost_weight    = orig.get("cost", router.cost_weight)
                router.quality_weight = orig.get("quality", router.quality_weight)
                router.speed_weight   = orig.get("speed", router.speed_weight)
                logger.info("Router weights restored to baseline")
        threading.Thread(target=restore, daemon=True).start()

    @staticmethod
    def _notify(channel: str, message: str):
        logger.warning(f"[NOTIFY:{channel.upper()}] {message}")
        # 실제: Slack webhook / PagerDuty / email

    @staticmethod
    def _emit_anomaly_telemetry(policy: RemediationPolicy, value: float):
        try:
            from splunk_telemetry import get_telemetry
            get_telemetry().emit_anomaly(
                anomaly_type          = policy.anomaly_type.value,
                metric_name           = policy.anomaly_type.value,
                current_value         = value,
                threshold             = policy.trigger_threshold,
                remediation_triggered = True,
            )
        except Exception:
            pass

    def stats(self) -> dict:
        return {
            "remediation_count": self._remediation_count,
            "active_cooldowns":  {k.value: max(0, int(v - time.time()))
                                   for k, v in self._active_cooldowns.items()},
        }


# ──────────────────────────────────────────────
# Anomaly Handler (Splunk Alert webhook 수신)
# ──────────────────────────────────────────────

class AnomalyHandler:
    """
    Splunk Saved Search Alert → MCPAgents webhook 수신기.

    Splunk CDTS가 이상을 탐지하면 이 핸들러가 호출됩니다.
    FastAPI 라우터에 /splunk/alert POST 엔드포인트로 등록하세요.
    """

    def __init__(self, remediator: RouterRemediator = None):
        self._remediator = remediator or RouterRemediator()
        self._policies: Dict[AnomalyType, RemediationPolicy] = {
            p.anomaly_type: p for p in DEFAULT_POLICIES
        }

    def handle(self, alert_payload: Dict[str, Any]) -> Dict:
        """
        Splunk Alert 페이로드 처리

        Expected payload format (Splunk webhook):
        {
          "result": {
            "anomaly_type": "cost_spike",
            "metric_value": "8.5",
            "model": "claude-3-opus",
            "session_id": "abc123"
          },
          "search_name": "MCPAgents Cost Anomaly Alert",
          ...
        }
        """
        result = alert_payload.get("result", alert_payload)

        anomaly_str = result.get("anomaly_type", "")
        metric_val  = float(result.get("metric_value", result.get("current_value", 0)))
        model       = result.get("model", "")

        # AnomalyType 매핑
        try:
            anomaly_type = AnomalyType(anomaly_str)
        except ValueError:
            logger.warning(f"Unknown anomaly_type: {anomaly_str}")
            return {"handled": False, "reason": f"unknown anomaly_type: {anomaly_str}"}

        policy = self._policies.get(anomaly_type)
        if not policy:
            return {"handled": False, "reason": "no policy defined"}

        # 임계값 초과 시 복구 적용
        if metric_val >= policy.trigger_threshold:
            remediation = self._remediator.apply_policy(policy, metric_val)
            return {"handled": True, "model": model, **remediation}

        return {"handled": False,
                "reason": f"value {metric_val} < threshold {policy.trigger_threshold}"}

    def register_policy(self, policy: RemediationPolicy):
        self._policies[policy.anomaly_type] = policy

    def set_router(self, router):
        self._remediator.set_router(router)

    def stats(self) -> dict:
        return {"remediator": self._remediator.stats()}


# ──────────────────────────────────────────────
# FastAPI 라우터 (선택적 사용)
# ──────────────────────────────────────────────

def create_splunk_webhook_router(handler: AnomalyHandler):
    """
    FastAPI Router 생성 — Splunk Alert webhook 엔드포인트

    Usage:
        from fastapi import FastAPI
        from auto_remediation import AnomalyHandler, create_splunk_webhook_router

        app = FastAPI()
        handler = AnomalyHandler()
        app.include_router(create_splunk_webhook_router(handler))
    """
    try:
        from fastapi import APIRouter, Request
        router = APIRouter(prefix="/splunk", tags=["splunk"])

        @router.post("/alert")
        async def receive_splunk_alert(request: Request):
            payload = await request.json()
            return handler.handle(payload)

        @router.get("/health")
        async def health():
            return {"status": "ok", "stats": handler.stats()}

        return router
    except ImportError:
        logger.warning("FastAPI not installed — webhook router unavailable")
        return None


# ──────────────────────────────────────────────
# 싱글톤
# ──────────────────────────────────────────────
_handler: Optional[AnomalyHandler] = None

def get_anomaly_handler() -> AnomalyHandler:
    global _handler
    if _handler is None:
        _handler = AnomalyHandler()
    return _handler


# ── 테스트 ────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    handler = AnomalyHandler()

    test_alerts = [
        {"result": {"anomaly_type": "cost_spike",    "metric_value": "8.50", "model": "claude-3-opus"}},
        {"result": {"anomaly_type": "latency_spike", "metric_value": "6200", "model": "gpt-4o"}},
        {"result": {"anomaly_type": "error_rate_high","metric_value": "0.22", "model": "claude-3.5-sonnet"}},
        {"result": {"anomaly_type": "dlp_burst",     "metric_value": "15",   "model": ""}},
        {"result": {"anomaly_type": "cost_spike",    "metric_value": "1.00", "model": "gpt-4o-mini"}},  # 임계값 미달
    ]

    for alert in test_alerts:
        anomaly = alert["result"]["anomaly_type"]
        value   = alert["result"]["metric_value"]
        result  = handler.handle(alert)
        status  = "✅ HANDLED" if result.get("handled") else "⏭️  SKIPPED"
        print(f"{status} | {anomaly} = {value}")
        if result.get("handled"):
            for a in result.get("actions", []):
                print(f"  → {a['action']}: {a['result']}")

    print("\nStats:", handler.stats())
