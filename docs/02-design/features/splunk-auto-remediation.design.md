# Design: splunk-auto-remediation

- **Phase**: Design
- **Created**: 2026-05-15
- **Ref**: `docs/01-plan/features/splunk-auto-remediation.plan.md`

---

## Architecture Overview

```
Splunk CDTS Saved Search Alert
    │
    ▼  POST /splunk/alert (FastAPI)
AnomalyHandler.handle(payload)
    │ anomaly_type + metric_value
    ▼
RouterRemediator.apply_policy(policy, value)
    │
    ├─ cost_spike      → cost_weight += 0.3, quality_weight -= 0.2
    │                    → _schedule_weight_restore(600s)
    ├─ latency_spike   → speed_weight = min(0.6, speed_weight + 0.2)
    ├─ error_rate_high → quality_weight += 0.1, cost_weight -= 0.1
    └─ dlp_burst       → notify_security (DLP strictness↑)
    │
    ▼  (emit_telemetry 액션)
SplunkTelemetry.emit_anomaly()  →  HEC index=mcp_agents
    │
    ▼  (쿨다운 종료 후)
_schedule_weight_restore() → IntelligentRouter 가중치 원복
```

---

## Current State 분석

### 이미 완성된 컴포넌트 (변경 없음)

| 파일 | 상태 |
|------|------|
| `auto_remediation.py` | ✅ AnomalyHandler, RouterRemediator, DEFAULT_POLICIES(4종), FastAPI 라우터, 싱글톤 |
| `multi_llm_platform/intelligent_router.py` | ✅ `IntelligentRouter(cost_weight, quality_weight, speed_weight)` |

### 수정 필요: `main.py`

`initialize_splunk_integration()` (line 23~58)에서 `handler = get_anomaly_handler()`(line 45)를 호출하지만
`handler.set_router(router)` 없이 종료된다.

**현재 코드 (line 44~46)**:
```python
# ④ Auto-Remediation Handler
handler = get_anomaly_handler()
logger.info(f"④ Auto-Remediation: ready ({len(handler._policies)} policies)")
```

**수정 후 (line 44~50)**:
```python
# ④ Auto-Remediation Handler
handler = get_anomaly_handler()
logger.info(f"④ Auto-Remediation: ready ({len(handler._policies)} policies)")

# IntelligentRouter 연결 (가중치 동적 조정 활성화)
try:
    from multi_llm_platform.intelligent_router import IntelligentRouter
    router = IntelligentRouter()
    handler.set_router(router)
    logger.info("  Router → AnomalyHandler connected")
except Exception as e:
    logger.warning(f"  Router connection skipped: {e}")
```

---

## 선택 작업: TOKEN_OVERRUN 정책 추가

`auto_remediation.py`의 `DEFAULT_POLICIES` 리스트에 추가:

```python
RemediationPolicy(
    anomaly_type      = AnomalyType.TOKEN_OVERRUN,
    trigger_threshold = 100000,   # 토큰/시간
    actions           = ["reduce_max_tokens", "enable_aggressive_caching", "emit_telemetry"],
    cooldown_sec      = 600,
),
```

추가 위치: `DEFAULT_POLICIES` 리스트의 `DLP_BURST` 항목 다음.

---

## Data Flow (cost_spike 시나리오)

```
Splunk CDTS: index=mcp_agents event_type=mcp_llm_call
    | stats sum(cost_usd) by _time span=1h
    | where total_cost > 5.0
    → Saved Search Alert 발화
    │
    ▼
POST /splunk/alert {"result": {"anomaly_type": "cost_spike", "metric_value": "8.50", "model": "claude-3-opus"}}
    │
    ▼
AnomalyHandler.handle()
  → AnomalyType.COST_SPIKE, value=8.50 ≥ threshold=5.0 → apply_policy()
    │
    ▼
RouterRemediator.apply_policy(COST_SPIKE_POLICY, 8.50)
  → action: "switch_to_cheaper_model"
      router.cost_weight    = 0.3 + 0.3 = 0.6
      router.quality_weight = 0.5 - 0.2 = 0.3
      _schedule_weight_restore(600s)   ← 백그라운드 스레드
  → action: "enable_aggressive_caching"  → "caching policy: aggressive"
  → action: "notify_admin"               → logger.warning("[NOTIFY:ADMIN] ...")
  → action: "emit_telemetry"             → get_telemetry().emit_anomaly(...)
  → cooldown: 600s 설정
    │
    ▼ (600초 후)
BackgroundThread: router.cost_weight=0.3, router.quality_weight=0.5 원복
```

---

## 변경 파일 목록

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `auto_remediation.py` | **(선택) 수정** | `TOKEN_OVERRUN` RemediationPolicy 추가 |
| `main.py` | **수정** | `IntelligentRouter()` + `handler.set_router()` (try/except 래핑) |
| `multi_llm_platform/intelligent_router.py` | **변경 없음** | 이미 완성 |

---

## Implementation Checklist

- [ ] `main.py` — `# ④` 블록에 try/except 래핑된 `IntelligentRouter()` + `handler.set_router(router)` 추가
- [ ] (선택) `auto_remediation.py` — `TOKEN_OVERRUN` RemediationPolicy 추가
- [ ] `python auto_remediation.py` 실행 — 4 HANDLED + 1 SKIPPED 확인
- [ ] router 연결 후: cost_spike → `cost_weight=0.6`(원래 0.3+boost 0.3) 확인
- [ ] SOAR Bridge, HEC Telemetry 기존 동작 무영향 확인

---

## Acceptance Criteria

| 기준 | 검증 방법 |
|------|-----------|
| `handler.set_router(router)` 완료 | `main.py:44-50` 코드 확인 |
| `cost_spike` → `cost_weight` 동적 조정 | `RouterRemediator._execute_action` 트레이스 |
| 쿨다운 후 가중치 원복 (`_schedule_weight_restore`) | `auto_remediation.py:206-216` 로직 확인 |
| router=None graceful degradation | `_execute_action` line 146 `"skipped (no router)"` 경로 |
| `python auto_remediation.py` 4 HANDLED + 1 SKIPPED | `__main__` 실행 결과 |
