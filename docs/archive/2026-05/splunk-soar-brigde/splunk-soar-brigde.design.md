# Design: splunk-soar-brigde

- **Phase**: Design
- **Created**: 2026-05-15
- **Ref**: `docs/01-plan/features/splunk-soar-brigde.plan.md`

---

## Architecture Overview

```
AdvancedMCPAgent.execute()
    │
    ▼  (각 tool 실행 후 결과)
DLPPolicyEngine.scan(result, OUTBOUND, tool_name, user_id)   ← [신규 연결]
    │ is_clean=False
    ▼
SOARBridge.on_dlp_violation(violation_dict)           ← [patched_scan 내부 자동 호출]
    ├─ SplunkFoundationSecScorer.score()
    │      └─ SPLUNK_API_TOKEN 있음 → Foundation-sec API
    │         없음              → heuristic fallback
    ├─ SplunkTelemetry.emit_dlp_violation()            ← HEC 항상 전송
    └─ risk_score ≥ 30 → SOAR REST API
           ├─ POST /rest/container   (컨테이너 생성)
           └─ POST /rest/playbook_run (플레이북 비동기 실행)
```

---

## Current State 분석

### 이미 완성된 컴포넌트 (변경 없음)

| 파일 | 상태 |
|------|------|
| `security/soar_bridge.py` | ✅ SOARBridge, Foundation-sec scorer, patch helper |
| `main.py` | ✅ `patch_dlp_engine_with_soar()` 호출 있음 |
| `enterprise_mcp_connector/dlp_policy.py` | ✅ scan() 시그니처 호환 |
| `.env.example` | ✅ SOAR 환경변수 포함 |

### 수정 필요: `advanced_agent.py`

`execute()` 메서드의 tool 실행 루프(line 276~292)에서 `result`를 DLP scan에 통과시키지 않는다.
`patch_dlp_engine_with_soar()`는 `main.py`에서 적용하지만 에이전트 인스턴스와 연결되지 않는다.

---

## Component Design

### `advanced_agent.py` — `__init__()` 수정

`AdvancedMCPAgent.__init__()` 끝에 lazy 초기화 필드 추가:

```python
# DLP + SOAR lazy init (graceful degradation)
self._dlp = None
self._soar = None
```

### `advanced_agent.py` — `execute()` 내 DLP lazy init

`execute()` 상단 telemetry init 블록 바로 아래에 추가:

```python
# DLP + SOAR 초기화 (lazy, 최초 1회)
try:
    if self._dlp is None:
        from enterprise_mcp_connector.dlp_policy import DLPPolicyEngine
        from security.soar_bridge import get_soar_bridge, patch_dlp_engine_with_soar
        self._dlp = DLPPolicyEngine()
        self._soar = get_soar_bridge()
        patch_dlp_engine_with_soar(self._dlp, self._soar)
except Exception:
    self._dlp = None
```

### `advanced_agent.py` — tool 실행 루프 내 DLP scan

기존 tool 실행 결과 직후(line 281 아래)에 DLP scan 삽입:

```python
# 기존 코드
result = await self._tools[tool_name](query, context)
results.append({"tool": tool_name, "result": result})

# ← 신규: outbound DLP scan (result = 에이전트 출력 = outbound)
try:
    if self._dlp:
        from enterprise_mcp_connector.dlp_policy import TransferDirection
        self._dlp.scan(
            result,
            TransferDirection.OUTBOUND,
            tool_name=tool_name,
            user_id=context.user_id,
        )
        # patched_scan이 내부적으로 SOARBridge.on_dlp_violation() 호출
except Exception:
    pass
```

---

## Data Flow (DLP 위반 시나리오)

```
query = "신용카드번호 4111-1111-1111-1111 처리해줘"
    │
    ▼
_tool_generate_code() → result = {"code": "...", "data": "4111-1111-1111-1111..."}
    │
    ▼
DLPPolicyEngine.scan(result, OUTBOUND, tool_name="generate_code", user_id="gyver")
  → DLP-001 Credit Card Detection 패턴 매칭
  → DLPViolation(rule_id="DLP-001", sensitivity=RESTRICTED, action_taken=BLOCK)
    │ (patched_scan 자동 호출)
    ▼
SOARBridge.on_dlp_violation({
    "rule_id": "DLP-001", "rule_name": "Credit Card Detection",
    "sensitivity": "RESTRICTED", "action_taken": "block",
    "tool_name": "generate_code", "user_id": "gyver", ...
})
    │
    ├─ SplunkFoundationSecScorer.score() → risk_score=75, level=HIGH
    ├─ emit_dlp_violation() → HEC index=mcp_agents
    └─ risk_score≥30 → POST /rest/container → POST /rest/playbook_run
           playbook: mcp_quarantine_session
```

---

## 변경 파일 목록

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `security/soar_bridge.py` | **변경 없음** | 이미 완성 |
| `main.py` | **변경 없음** | 이미 완성 |
| `advanced_agent.py` | **수정** | `__init__`에 `_dlp/_soar` 필드 + `execute()`에 lazy init + DLP scan 블록 |

---

## Implementation Checklist

- [ ] `advanced_agent.py` — `__init__()` 끝에 `self._dlp = None`, `self._soar = None` 추가
- [ ] `advanced_agent.py` — `execute()` 상단 DLP lazy init 블록 추가 (try/except)
- [ ] `advanced_agent.py` — tool 실행 루프 내 `self._dlp.scan(result, OUTBOUND, ...)` 추가 (try/except)
- [ ] 검증: `python security/soar_bridge.py` — 3개 test violation 실행
- [ ] 검증: SOAR disabled(토큰 없음) → HEC emit만, 에러 없음
- [ ] 검증: heuristic — TOP_SECRET+BLOCK → score≥80 → CRITICAL → mcp_block_user 플레이북

---

## Acceptance Criteria

| 기준 | 검증 방법 |
|------|-----------|
| tool 결과가 DLP scan을 경유 | `advanced_agent.py` 코드 확인 |
| DLP 위반 → `on_dlp_violation()` 자동 호출 | patched_scan 경로 트레이스 |
| SOAR disabled → HEC만 전송, 에러 없음 | `soar_bridge.py __main__` 실행 |
| 기존 기능(HEC 텔레메트리, Splunk query) 무영향 | try/except 래핑으로 격리 보장 |
