# Plan: splunk-soar-brigde

- **Phase**: Plan
- **Created**: 2026-05-15
- **Week**: 3 (2026-06-01 ~ 2026-06-07)
- **Feature**: DLP → Splunk SOAR Security Bridge

---

## Goal

DLP 위반이 탐지될 때 Foundation-sec 모델로 위험도를 재평가하고,
Splunk SOAR 자동 플레이북을 트리거하는 보안 자동화 루프를 완성한다.

```
DLPPolicyEngine.scan() 위반 감지
    → SplunkFoundationSecScorer (Foundation-sec 또는 휴리스틱 폴백)
    → SOARBridge.on_dlp_violation()
        ├─ Splunk HEC: emit_dlp_violation() — 항상
        └─ [risk_score ≥ 30] → SOAR REST API
               ├─ POST /rest/container  (컨테이너 생성)
               └─ POST /rest/playbook_run (플레이북 실행)
```

---

## 현재 상태 분석

| 파일 | 상태 | 비고 |
|------|------|------|
| `security/soar_bridge.py` | ✅ **완성** | SOARBridge, Foundation-sec scorer, patch helper, singleton |
| `security/__init__.py` | ✅ **완성** | SOARBridge export |
| `main.py` | ✅ **완성** | `initialize_splunk_integration()` — SOAR 초기화 + DLP patch |
| `.env.example` | ✅ **완성** | SPLUNK_SOAR_URL, SPLUNK_SOAR_TOKEN, SPLUNK_FOUNDATION_SEC_URL 포함 |
| `enterprise_mcp_connector/dlp_policy.py` | ✅ **완성** | scan() 시그니처 soar_bridge와 완전 호환 |
| `advanced_agent.py` | ❌ **연결 누락** | tool 호출 시 DLP scan 경유하지 않음 |

### 핵심 갭

`main.py`에서 `patch_dlp_engine_with_soar(dlp, bridge)`를 적용하지만,
패치된 `dlp` 인스턴스가 `AdvancedMCPAgent`에 전달되지 않는다.
에이전트가 도구를 실행할 때 outbound 데이터가 DLP scan을 거치지 않아
SOAR bridge가 실제로 트리거되지 않는다.

---

## Scope (Do Phase 작업 목록)

### 필수 (Do Phase)

1. **`advanced_agent.py` — outbound DLP scan 연결**
   - `_execute_tool()` 또는 각 `_tool_*()` 메서드의 결과(outbound 데이터)를
     `DLPPolicyEngine.scan()` + SOAR bridge에 통과시킨다
   - 패턴: 기존 `try/except Exception: pass` graceful degradation 유지

2. **DLP engine 인스턴스 공유 방식 결정**
   - Option A: `AdvancedMCPAgent.__init__`에 `DLPPolicyEngine` 인스턴스 주입 (권장)
   - Option B: `advanced_agent.py` 내에서 `get_soar_bridge()` + `patch_dlp_engine_with_soar()` lazy 초기화

3. **통합 흐름 테스트**
   - `python security/soar_bridge.py` — 내장 `__main__` 블록 실행
   - SOAR disabled(토큰 없음) 상태에서 HEC telemetry만 emit 확인
   - heuristic scorer: RESTRICTED/BLOCK → risk_score ≥ 60 → HIGH 레벨 확인

### 선택 (시간 여유 시)

4. **`advanced_agent.py` — inbound DLP scan**
   - 에이전트가 외부 도구로부터 수신한 결과(inbound)도 scan 옵션

5. **`splunk_telemetry.py` `emit_dlp_violation()` 시그니처 확인**
   - `soar_bridge._emit_telemetry()`에서 전달하는 필드가 HEC client와 호환되는지 확인

---

## Acceptance Criteria

| 기준 | 검증 방법 |
|------|-----------|
| `bridge.on_dlp_violation(dict)` → risk 평가 → HEC emit | `python security/soar_bridge.py` 실행 후 로그 확인 |
| SOAR disabled 시 graceful degradation (HEC만 전송) | `SPLUNK_SOAR_URL` 미설정 상태에서 실행 |
| `advanced_agent.py` tool 결과 → DLP scan → (위반 시) `on_dlp_violation()` | 신용카드 번호가 포함된 mock 결과로 트리거 테스트 |
| Foundation-sec fallback: 휴리스틱 스코어 정확도 | TOP_SECRET+BLOCK → score ≥ 80 → CRITICAL 확인 |

---

## 변경 파일 목록

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `security/soar_bridge.py` | **변경 없음** | 이미 완성 |
| `main.py` | **변경 없음** | 이미 완성 |
| `advanced_agent.py` | **수정** | outbound DLP scan + SOAR bridge 연결 |

---

## Implementation Checklist

- [ ] `advanced_agent.py` — `_execute_tool()` 또는 `execute()` 내 outbound DLP scan 추가
- [ ] DLP engine + SOAR bridge graceful degradation (`try/except` 패턴)
- [ ] `python security/soar_bridge.py` 실행 — 3개 test violation 모두 통과
- [ ] SOAR disabled 경로 (`enabled=False`) 로그 확인
- [ ] heuristic scorer: TOP_SECRET+BLOCK → CRITICAL, RESTRICTED+BLOCK → HIGH 확인
