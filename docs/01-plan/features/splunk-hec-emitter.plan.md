# Plan: splunk-hec-emitter

## Overview
MCPAgents의 모든 운영 이벤트(LLM 호출, 비용, 레이턴시, 에러, DLP 위반, 캐시, 라우터 결정)를
Splunk HTTP Event Collector(HEC)로 비동기 배치 전송하는 텔레메트리 에미터.

- **Status**: Plan
- **Created**: 2026-05-15
- **Priority**: P0 (다른 모듈의 선행 조건)
- **Week**: Week 1 (5/18–5/24)

---

## Goals

1. `splunk_telemetry.py`의 `SplunkHECClient` + `SplunkTelemetry` 클래스를 실제 Splunk에 연결
2. `advanced_agent.py`와 `multi_llm_platform/` 모듈에 텔레메트리 훅 삽입
3. Splunk `mcp_agents` 인덱스에서 이벤트 실시간 확인 가능
4. 로컬(`docker-compose`) 및 Splunk Cloud 모두에서 동작 검증

---

## Scope

### In Scope
- `splunk_telemetry.py` — HEC 클라이언트 완성 (배치, 재시도, 통계)
- `advanced_agent.py` — `emit_agent_start/complete/error` 훅 삽입
- `multi_llm_platform/llm_router.py` — `emit_llm_call`, `emit_router_decision` 훅
- `multi_llm_platform/semantic_cache.py` — `emit_cache_hit/miss` 훅
- `splunk_app/default/indexes.conf` — `mcp_agents` 인덱스 확인
- `.env` / `docker-compose.yml` — HEC 포트(8088) 설정 검증
- 연결 테스트 스크립트 (`python splunk_telemetry.py`)

### Out of Scope
- Splunk MCP Server 연동 (② 모듈)
- SOAR webhook (③ 모듈)
- 대시보드 교체 (⑤ 모듈)

---

## Acceptance Criteria

- [ ] `python splunk_telemetry.py` 실행 시 stats `sent > 0`, `dropped = 0`
- [ ] Splunk Search: `index=mcp_agents | head 10` → 이벤트 10개 이상 확인
- [ ] 각 이벤트 타입(llm_call, tool_call, router_decision, dlp_violation, cache_hit) 최소 1개씩 인덱싱
- [ ] `advanced_agent.py`가 요청 처리 시 자동으로 Splunk에 이벤트 전송
- [ ] HEC 토큰 미설정 시 graceful degradation (경고 로그만, 에러 없음)

---

## Implementation Order

1. **환경 검증** — `.env` HEC 설정, `docker-compose` HEC 포트 노출 확인
2. **인덱스 확인** — `splunk_app/default/indexes.conf`의 `mcp_agents` 인덱스 생성 확인
3. **HEC 연결 테스트** — `python splunk_telemetry.py` 단독 실행으로 기본 동작 검증
4. **훅 삽입** — `advanced_agent.py` → `multi_llm_platform/` 순서로 emit 호출 추가
5. **통합 테스트** — `python main.py`로 전체 플로우 실행 후 Splunk에서 이벤트 확인

---

## Key Files

| 파일 | 역할 |
|------|------|
| `splunk_telemetry.py` | HEC 클라이언트 + 이벤트 파사드 (이미 구현됨) |
| `advanced_agent.py` | 에이전트 실행 훅 삽입 대상 |
| `multi_llm_platform/llm_router.py` | LLM 호출/라우터 결정 훅 대상 |
| `multi_llm_platform/semantic_cache.py` | 캐시 이벤트 훅 대상 |
| `splunk_app/default/indexes.conf` | 인덱스 설정 |
| `docker-compose.yml` | HEC 포트 8088 노출 확인 |
| `.env` | `SPLUNK_HEC_TOKEN`, `SPLUNK_HEC_URL` |

---

## Dependencies

- Splunk 로컬 인스턴스 실행 (`docker-compose up`)
- HEC 토큰 발급 (Splunk Web → Settings → Data Inputs → HTTP Event Collector)
- `mcp_agents` 인덱스 생성

---

## Risks

| 리스크 | 대응 |
|--------|------|
| HEC 포트 8088 미노출 | `docker-compose.yml` ports 섹션 확인 후 추가 |
| SSL 인증서 오류 | 로컬은 SSL 비활성화, Cloud는 verify=True |
| 인덱스 미생성 시 이벤트 유실 | `indexes.conf`로 사전 생성 또는 Splunk Web에서 수동 생성 |
| 배치 큐 오버플로우 | `maxsize=10_000`, `dropped` 카운터로 모니터링 |
