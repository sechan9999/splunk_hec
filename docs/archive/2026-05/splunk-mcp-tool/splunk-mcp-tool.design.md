# Design: splunk-mcp-tool

- **Phase**: Design
- **Created**: 2026-05-15
- **Ref**: `docs/01-plan/features/splunk-mcp-tool.plan.md`

---

## Architecture Overview

```
AdvancedMCPAgent._tools["splunk_query"]
        │
        ▼  (자연어 쿼리 입력)
SplunkPlugin.call("splunk_query", {"query": "...", "timerange": "-1h"})
        │
        ▼
SplunkMCPTool.execute(query, timerange)
        ├─ [MCP Server 가용]  → _query_via_mcp_server()  → SPLUNK_MCP_SERVER_URL
        └─ [REST fallback]    → SplunkRESTClient.run_search()
                                    → http://localhost:8089/services/search/jobs
                                          │
                                          ▼
                                    index=mcp_agents (SPL 실행)
                                          │
                                          ▼
                              results + summary → 에이전트 응답
```

---

## Current State 분석

### `tools/splunk_mcp_tool.py` — **구현 완료** (변경 없음)

| 컴포넌트 | 상태 | 비고 |
|----------|------|------|
| `SPL_TEMPLATES` (10종) | ✅ 완성 | hourly_cost, error_rate, dlp_violations 등 |
| `NL_KEYWORD_MAP` | ✅ 완성 | 한/영 키워드 매핑 |
| `SplunkRESTClient` | ✅ 완성 | POST jobs → poll results |
| `SplunkMCPTool.execute()` | ✅ 완성 | MCP Server + REST fallback |
| `register_splunk_tool()` | ✅ 완성 | `_tools` dict 직접 주입 가능 |

### `enterprise_mcp_connector/tool_manager.py` — **수정 필요**

현재 `PLUGIN_REGISTRY`에 `google_drive`, `slack`, `github`만 등록됨.
`ToolManager.register_tool()`은 `ToolConfig`를 받고 `PLUGIN_REGISTRY`에서 플러그인을 찾음.
→ `SplunkPlugin(MCPServerPlugin)` 클래스 추가 + `PLUGIN_REGISTRY["splunk"]` 등록 필요.

### `advanced_agent.py` — **수정 필요**

`_register_default_tools()`의 `self._tools` dict에 `splunk_query` 항목 추가.

---

## Component Design

### 1. `SplunkPlugin(MCPServerPlugin)` — tool_manager.py에 추가

기존 플러그인 패턴(`GoogleDrivePlugin`, `SlackPlugin`)과 동일한 구조:

```python
class SplunkPlugin(MCPServerPlugin):
    def __init__(self, config: ToolConfig):
        super().__init__(config)
        from tools.splunk_mcp_tool import SplunkMCPTool
        self._splunk = SplunkMCPTool()
        self._methods = {
            "splunk_query": ToolMethod(
                name="splunk_query",
                description="Natural language or SPL query on index=mcp_agents",
                parameters={
                    "query":       {"type": "string"},
                    "timerange":   {"type": "string", "default": "-1h"},
                    "max_results": {"type": "integer", "default": 50}
                },
                returns={"results": "array", "spl": "string", "summary": "string"},
                requires_permission=PermissionLevel.READ_ONLY
            )
        }

    async def connect(self) -> bool:
        self.config.status = ToolStatus.ACTIVE
        logger.info("✅ SplunkPlugin connected")
        return True

    async def disconnect(self) -> None:
        self.config.status = ToolStatus.INACTIVE

    async def health_check(self) -> bool:
        return self._splunk._mcp_available or bool(self._splunk._rest.base_url)

    async def call(self, method: str, params: Dict) -> Any:
        if method == "splunk_query":
            return self._splunk.execute(**params)
        raise ValueError(f"Unknown method: {method}")
```

**등록 위치**: `tool_manager.py` — `PLUGIN_REGISTRY` 딕셔너리

```python
# tool_manager.py 기존 코드
PLUGIN_REGISTRY: Dict[str, type] = {
    "google_drive": GoogleDrivePlugin,
    "slack":        SlackPlugin,
    "github":       GitHubPlugin,
    "splunk":       SplunkPlugin,   # ← 추가
}
```

---

### 2. `advanced_agent.py` — `_register_default_tools()` 수정

```python
def _register_default_tools(self):
    self._tools = {
        "get_docs":      self._tool_get_docs,
        "browse_web":    self._tool_browse_web,
        "search_web":    self._tool_search_web,
        "extract_data":  self._tool_extract_data,
        "generate_code": self._tool_generate_code,
        "analyze_data":  self._tool_analyze_data,
        "remember":      self._tool_remember,
        "recall":        self._tool_recall,
        "splunk_query":  self._tool_splunk_query,   # ← 추가
    }
```

신규 메서드 `_tool_splunk_query()` 추가:

```python
async def _tool_splunk_query(self, query: str, context: AgentContext) -> Dict:
    try:
        from tools.splunk_mcp_tool import SplunkMCPTool
        tool = SplunkMCPTool()
        return tool.execute(query, timerange="-1h")
    except Exception as e:
        return {"error": str(e), "results": [], "summary": "Splunk query failed"}
```

**쿼리 분석 확장** — `_analyze_query()`에서 Splunk 도구 트리거:

```python
# 기존 requires_docs / requires_web에 추가
if any(w in query_lower for w in ["비용", "cost", "에러", "dlp", "splunk",
                                    "캐시", "레이턴시", "이상", "라우터", "사용자"]):
    analysis["requires_splunk"] = True

# _select_tools()에 추가
if analysis.get("requires_splunk"):
    tools.append("splunk_query")
```

---

### 3. ToolManager 초기화 코드 (main.py 또는 enterprise_connector)

```python
from enterprise_mcp_connector.tool_manager import ToolManager, ToolConfig, ToolCategory

tm = ToolManager()
tm.register_tool(ToolConfig(
    tool_id="splunk",
    name="Splunk Analytics",
    description="MCPAgents operational data via Splunk",
    category=ToolCategory.ANALYTICS,
    server_url=os.environ.get("SPLUNK_API_URL", "http://localhost:8089"),
    icon="🔍",
    tags=["splunk", "observability", "analytics", "mcp"]
))
await tm.connect_tool("splunk")
```

---

## Data Flow (자연어 쿼리 예시)

```
사용자: "지난 1시간 Claude 호출 비용 얼마야?"
    │
    ▼
AdvancedMCPAgent._analyze_query()
  → requires_splunk = True (키워드: "비용", "비용")
    │
    ▼
_select_tools() → ["splunk_query"]
    │
    ▼
_tool_splunk_query(query="지난 1시간 Claude 호출 비용 얼마야?")
    │
    ▼
SplunkMCPTool._nl_to_spl()
  → 키워드 "비용" 매칭 → SPL_TEMPLATES["hourly_cost"]
  → "index=mcp_agents event_type=mcp_llm_call earliest=-1h | stats sum(cost_usd) ..."
    │
    ▼
SplunkRESTClient.run_search(spl)  (또는 MCP Server)
    │
    ▼
{"results": [{"model": "claude-3.5-sonnet", "total_cost_usd": "0.0234"}],
 "summary": "Found 1 row. Top: {'model': 'claude...', 'total_cost_usd': '0.0234'}"}
    │
    ▼
에이전트 응답: "지난 1시간 Claude 호출 비용은 $0.023입니다."
```

---

## 변경 파일 목록

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `tools/splunk_mcp_tool.py` | **변경 없음** | 이미 완성 |
| `enterprise_mcp_connector/tool_manager.py` | **수정** | `SplunkPlugin` 클래스 + `PLUGIN_REGISTRY` 항목 추가 |
| `advanced_agent.py` | **수정** | `splunk_query` 도구 등록 + `_tool_splunk_query()` + `_analyze_query()` 키워드 확장 |

---

## Implementation Checklist

- [ ] `tool_manager.py` — `SplunkPlugin(MCPServerPlugin)` 클래스 추가
- [ ] `tool_manager.py` — `PLUGIN_REGISTRY["splunk"] = SplunkPlugin` 추가
- [ ] `advanced_agent.py` — `_tool_splunk_query()` 메서드 추가
- [ ] `advanced_agent.py` — `_register_default_tools()`에 `splunk_query` 등록
- [ ] `advanced_agent.py` — `_analyze_query()`에 Splunk 키워드 트리거 추가
- [ ] `advanced_agent.py` — `_select_tools()`에 `requires_splunk` 처리 추가
- [ ] 통합 테스트: `agent.execute("지난 1시간 LLM 비용 얼마야?")` → results 포함 응답

---

## Acceptance Criteria (Plan 문서 대응)

| 기준 | 검증 방법 |
|------|-----------|
| `agent.execute("비용 얼마야?")` → SPL 실행 → 결과 반환 | `python advanced_agent.py` 실행 후 splunk_query 단계 확인 |
| `PLUGIN_REGISTRY["splunk"]` 등록 확인 | `tool_manager.py` 코드 확인 |
| MCP 토큰 미설정 → REST API fallback | `SPLUNK_MCP_SERVER_URL` 미설정 시 `_mcp_available=False` 경로 확인 |
| `index=mcp_agents` 쿼리 결과 포함 | SPL 로그 확인 |
