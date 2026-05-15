# Plan: splunk-auto-remediation

- **Phase**: Plan
- **Created**: 2026-05-15
- **Week**: 4 (2026-06-08 ~ 2026-06-14)
- **Feature**: Splunk Anomaly → MCPAgents Auto-Remediation Loop

---

## Goal

Splunk Saved Search Alert(CDTS 이상 탐지)가 webhook으로 도착하면
`IntelligentRouter`의 가중치를 자동으로 조정하여 비용·레이턴시·에러율 문제를
운영자 개입 없이 자동 복구한다.

```
Splunk CDTS Saved Search Alert
    → POST /splunk/alert (FastAPI webhook)
    → AnomalyHandler.handle()
    → RouterRemediator.apply_policy()
        ├─ cost_spike      → cost_weight↑, switch_to_cheaper_model
        ├─ latency_spike   → speed_weight↑, switch_to_faster_model
        ├─ error_rate_high → quality_weight↑, circuit_breaker_open
        └─ dlp_burst       → dlp_strictness↑, notify_security
    → SplunkTelemetry.emit_anomaly()  (HEC)
    → 쿨다운 후 IntelligentRouter 가중치 원복
```

---

## 현재 상태 분석

| 파일 | 상태 | 비고 |
|------|------|------|
| `auto_remediation.py` | ✅ **완성** | AnomalyHandler, RouterRemediator, DEFAULT_POLICIES(4종), FastAPI 라우터, 싱글톤 |
| `main.py` | ⚠️ **부분 연결** | `get_anomaly_handler()` + `create_splunk_webhook_router()` ✅ / `handler.set_router()` ❌ |
| `multi_llm_platform/intelligent_router.py` | ✅ **완성** | `IntelligentRouter.cost_weight`, `quality_weight`, `speed_weight` 속성 존재 |
| `.env.example` | ✅ **완성** | `MCPAGENTS_WEBHOOK_URL`, `MCPAGENTS_WEBHOOK_PORT` 포함 |

### 핵심 갭

`main.py`의 `initialize_splunk_integration()`에서 `handler = get_anomaly_handler()`를 호출하지만
`handler.set_router(router)` — 즉 실제 `IntelligentRouter` 인스턴스를 AnomalyHandler에 전달하지 않는다.

결과: Splunk Alert가 도착해도 `RouterRemediator`의 `_router=None`이라
`switch_to_cheaper_model` 등 Router 조정 액션이 `"skipped (no router)"`로 무시된다.
`notify_*` + `emit_telemetry` 액션만 동작하고 실제 라우터 정책 변경이 일어나지 않는다.

### 추가 관찰

- `TOKEN_OVERRUN` AnomalyType이 enum에 정의되어 있으나 `DEFAULT_POLICIES`에 누락됨 (선택 작업)
- `RouterRemediator._execute_action("reduce_max_tokens")`가 실제 router 속성 변경 없이 문자열만 반환 — 향후 확장 가능

---

## Scope (Do Phase 작업 목록)

### 필수

1. **`main.py` — `initialize_splunk_integration()` 수정**
   - `IntelligentRouter()` 인스턴스 생성 후 `handler.set_router(router)` 호출
   - `multi_llm_platform.intelligent_router` import 추가

2. **통합 테스트**
   - `python auto_remediation.py` — 5개 test alert 실행
   - HANDLED: cost_spike(8.50), latency_spike(6200), error_rate_high(0.22), dlp_burst(15)
   - SKIPPED: cost_spike(1.00) — 임계값 미달

### 선택

3. **`auto_remediation.py` — `TOKEN_OVERRUN` 정책 추가**
   ```python
   RemediationPolicy(
       anomaly_type=AnomalyType.TOKEN_OVERRUN,
       trigger_threshold=100000,  # 토큰/시간
       actions=["reduce_max_tokens", "enable_aggressive_caching", "emit_telemetry"],
       cooldown_sec=600,
   )
   ```

4. **쿨다운 후 가중치 원복 검증** (`_schedule_weight_restore()`)

---

## Acceptance Criteria

| 기준 | 검증 방법 |
|------|-----------|
| `handler.set_router(router)` 연결 완료 | `main.py` 코드 확인 |
| `cost_spike` alert → `cost_weight` 증가 → 쿨다운 후 원복 | `RouterRemediator` 로직 트레이스 |
| `python auto_remediation.py` — 4개 HANDLED, 1개 SKIPPED | `__main__` 블록 실행 |
| router=None → `"skipped (no router)"` graceful degradation | `_execute_action()` 코드 확인 |
| Splunk `/splunk/alert` POST → FastAPI 정상 응답 | `create_splunk_webhook_router()` 트레이스 |

---

## 변경 파일 목록

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `auto_remediation.py` | **변경 없음** (선택: TOKEN_OVERRUN 정책 추가) | 이미 완성 |
| `main.py` | **수정** | `IntelligentRouter()` 생성 + `handler.set_router()` |
| `multi_llm_platform/intelligent_router.py` | **변경 없음** | 이미 완성 |

---

## Implementation Checklist

- [ ] `main.py` — `from multi_llm_platform.intelligent_router import IntelligentRouter` import 추가
- [ ] `main.py` — `initialize_splunk_integration()`에 `router = IntelligentRouter()` + `handler.set_router(router)` 추가
- [ ] `python auto_remediation.py` 실행 — 4 HANDLED + 1 SKIPPED 확인
- [ ] (선택) `auto_remediation.py` — `TOKEN_OVERRUN` RemediationPolicy 추가
