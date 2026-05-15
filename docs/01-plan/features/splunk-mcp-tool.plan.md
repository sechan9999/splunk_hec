# Plan: splunk-mcp-tool

## Overview
Splunk MCP Server(2026 GA)를 기존 Tool Manager에 새 커넥터로 등록하여,
에이전트가 자연어로 Splunk 데이터를 쿼리하는 양방향 연결을 구현.

- **Status**: Plan
- **Created**: 2026-05-15
- **Priority**: P1 (① HEC Emitter 완료 후 핵심 차별화 포인트)
- **Week**: Week 2 (5/25–5/31)

---

## Goals

1. `tools/splunk_mcp_tool.py`의 뼈대를 Splunk MCP Server GA API에 맞게 완성
2. `enterprise_mcp_connector/tool_manager.py`에 Splunk MCP 커넥터 등록
3. 에이전트가 "지난 1시간 Claude 호출 비용 얼마야?" 같은 자연어 쿼리로 Splunk 검색 가능
4. SPL 자동 생성 + 결과 반환 플로우 검증

---

## Scope

### In Scope
- `tools/splunk_mcp_tool.py` — Splunk MCP Server 클라이언트 완성
- `enterprise_mcp_connector/tool_manager.py` — 새 커넥터 등록
- `enterprise_mcp_connector/mcp_tools.py` — Splunk 쿼리 도구 추가
- `.env` — `SPLUNK_MCP_SERVER_URL`, `SPLUNK_MCP_TOKEN` 설정
- 자연어 → SPL 변환 + 결과 파싱 플로우

### Out of Scope
- SOAR webhook (③ 모듈)
- 대시보드 교체 (⑤ 모듈)
- Splunk Cloud 프로덕션 배포

---

## Acceptance Criteria

- [ ] `agent.execute("지난 1시간 Claude 호출 비용 얼마야?")` → Splunk SPL 실행 → 비용 반환
- [ ] Tool Manager에 `splunk_search` 도구 등록 확인
- [ ] `index=mcp_agents` 쿼리 결과가 에이전트 응답에 포함
- [ ] MCP 토큰 미설정 시 graceful degradation

---

## Implementation Order

1. **`tools/splunk_mcp_tool.py` 완성** — MCP Server API 클라이언트
2. **`tool_manager.py` 커넥터 등록** — `splunk_search`, `splunk_alert` 도구 추가
3. **자연어 → SPL 변환** — 쿼리 파서 or LLM 프롬프트
4. **`advanced_agent.py` 연동** — `_tools` 레지스트리에 Splunk 도구 추가
5. **통합 테스트** — 실제 Splunk에 쿼리 후 결과 확인

---

## Key Files

| 파일 | 역할 |
|------|------|
| `tools/splunk_mcp_tool.py` | Splunk MCP 클라이언트 (뼈대 존재) |
| `enterprise_mcp_connector/tool_manager.py` | 도구 레지스트리 |
| `enterprise_mcp_connector/mcp_tools.py` | MCP 도구 정의 |
| `advanced_agent.py` | 에이전트 도구 등록 |
| `.env` | `SPLUNK_MCP_SERVER_URL`, `SPLUNK_MCP_TOKEN` |

---

## Dependencies

- ① HEC Emitter 완료 (✅ Match Rate 96%)
- Splunk MCP Server GA 엔드포인트 접근
- `SPLUNK_MCP_TOKEN` 발급

---

## Risks

| 리스크 | 대응 |
|--------|------|
| Splunk MCP Server 로컬 미지원 | REST API fallback (`/services/search/jobs`) |
| 자연어→SPL 변환 정확도 | 고정 SPL 템플릿 + 파라미터 치환으로 MVP |
| 토큰 권한 부족 | `index=mcp_agents` 읽기 권한 확인 |
