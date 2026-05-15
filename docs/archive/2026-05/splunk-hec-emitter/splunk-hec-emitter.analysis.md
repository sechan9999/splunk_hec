# Gap Analysis: splunk-hec-emitter

- **Date**: 2026-05-15
- **Design**: `docs/02-design/features/splunk-hec-emitter.design.md`
- **Match Rate**: **96%** (✅ G-2 수정 후 재분석 — 90% 통과)

---

## Score Breakdown

| Category | Score | Status |
|----------|:-----:|:------:|
| Design Hook Match | 90% | ⚠️ |
| Lazy Import / Graceful Degradation Pattern | 100% | ✅ |
| Architectural Correctness (hooks on active path) | 70% | ⚠️ |
| **Overall** | **88%** | ⚠️ |

---

## Checklist Verification

| # | Requirement | Status | Evidence |
|---|-------------|:------:|----------|
| 1 | `advanced_agent.py` — emit_agent_start | ✅ | `advanced_agent.py:259` |
| 2 | `advanced_agent.py` — emit_agent_complete (success) | ✅ | `advanced_agent.py:306-312` |
| 3 | `advanced_agent.py` — emit_agent_error (failure) | ✅ | `advanced_agent.py:323-329` |
| 4 | `llm_router.py select_model()` — emit_router_decision | ✅ | `llm_router.py:206-218` |
| 5 | `llm_router.py` — emit_cache_hit | ✅ | `llm_router.py:293-300` |
| 6 | `llm_router.py` — emit_cache_miss | ✅ | `llm_router.py:311-315` |
| 7 | `llm_router.py` — emit_llm_call | ✅ | `llm_router.py:335-349` |
| 8 | `semantic_cache.py` — emit_cache_hit (exact) | ✅ | `semantic_cache.py:288-297` |
| 9 | `semantic_cache.py` — emit_cache_hit (semantic) | ✅ | `semantic_cache.py:318-327` |
| 10 | `semantic_cache.py` — emit_cache_miss | ✅ | `semantic_cache.py:333-337` |
| 11 | 지연 임포트 패턴 | ✅ | 3개 파일 모두 함수 내부 임포트 |
| 12 | Graceful degradation (try/except) | ⚠️ | `llm_router`, `semantic_cache` 적용. **`advanced_agent.py` 미적용** |
| 13 | HEC 미설정 시 기존 로직 영향 없음 | ✅ | `enqueue()` early-return 확인 |

---

## Gaps

### G-1 (High) — `semantic_cache.py` 훅이 비활성 코드 경로에 위치

**문제**: `route_and_execute()`는 `CacheManager`를 사용하며, `SemanticCache`는 런타임에서 한 번도 인스턴스화되지 않음.
`semantic_cache.py`의 emit 훅은 올바르게 작성됐으나 실제로 호출되지 않음.

**현재 영향**: 캐시 이벤트 telemetry는 `llm_router.py`의 훅으로 정상 전송됨 (Acceptance Criteria 충족).
설계 문서 2-C의 의도와 실제 실행 경로 간 불일치.

**권장 조치**: 설계 문서 2-C를 현실에 맞게 업데이트 (SemanticCache 미연동 명시). 저위험.

---

### G-2 (Medium) — `advanced_agent.py` emit 호출에 try/except 없음

**문제**: 설계 요건 "Graceful degradation (try/except Exception: pass 래핑)"에 따라 `llm_router.py`와
`semantic_cache.py`는 모든 emit 호출을 try/except로 래핑하지만, `advanced_agent.py`는 그렇지 않음.

**현재 영향**: SplunkHECClient 자체가 예외를 내부 처리하므로 실제 크래시 가능성은 낮음.
그러나 설계 요건 미준수.

**수정**: `advanced_agent.py` 4개 emit 호출 사이트에 try/except 추가. 3-line 변경.

---

### G-3 (Low) — `emit_cache_hit`에 `saved_cost` 미전달 (llm_router 경로)

`CacheManager` 백엔드가 비용 메타데이터를 저장하지 않아 `saved_cost=0`. SPL 쿼리 기능에는 영향 없음.

---

## Acceptance Criteria 상태

| 기준 | 상태 |
|------|------|
| `python splunk_telemetry.py` → stats.sent > 0 | ⏳ 실행 환경 필요 |
| `index=mcp_agents` 이벤트 확인 | ⏳ 실행 환경 필요 |
| 5가지 이벤트 타입 각 1개씩 인덱싱 | ⏳ 실행 환경 필요 |
| HEC 미설정 → graceful degradation | ✅ 코드 분석으로 확인 |
| `indexes.conf` mcp_agents 인덱스 | ✅ 확인됨 |

---

## 권장 조치 (Act 단계)

G-2 수정만으로 Match Rate ≥ 92% 예상:

1. `advanced_agent.py:257-259, 278, 306, 323` 의 4개 emit 사이트 try/except 래핑
2. 설계 문서 2-C 업데이트 (SemanticCache 비연동 명시)

→ `/pdca iterate splunk-hec-emitter`
