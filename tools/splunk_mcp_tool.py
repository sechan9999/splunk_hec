# tools/splunk_mcp_tool.py
"""
② Splunk MCP Server Tool Connector
Tool Manager에 Splunk MCP Server를 커넥터로 등록합니다.

에이전트가 자연어로 Splunk 데이터를 쿼리할 수 있게 됩니다.
예: "지난 1시간 Claude 호출 비용 얼마야?"
    → SPL: index=mcp_agents event_type=mcp_llm_call earliest=-1h | stats sum(cost_usd) as total_cost

References:
    https://help.splunk.com/en/splunk-observability-cloud/splunk-ai-assistant/
    interact-with-your-observability-data-using-the-splunk-mcp-server
"""

import json
import os
import time
import logging
from typing import Any, Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# SPL 쿼리 템플릿 (NL → SPL 변환 기반)
# ──────────────────────────────────────────────

SPL_TEMPLATES = {
    "hourly_cost": """
index=mcp_agents event_type=mcp_llm_call earliest={timerange}
| stats sum(cost_usd) as total_cost_usd,
        count as call_count,
        sum(total_tokens) as total_tokens
  by model
| sort -total_cost_usd
""",
    "error_rate": """
index=mcp_agents event_type=mcp_llm_call earliest={timerange}
| stats count as total,
        sum(eval(if(success="False",1,0))) as errors
  by model
| eval error_rate=round(errors/total*100, 2)
| sort -error_rate
""",
    "dlp_violations": """
index=mcp_agents event_type=mcp_dlp_violation earliest={timerange}
| stats count as violations by rule_name, action_taken, sensitivity
| sort -violations
""",
    "model_latency": """
index=mcp_agents event_type=mcp_llm_call earliest={timerange}
| stats avg(latency_ms) as avg_ms,
        perc95(latency_ms) as p95_ms,
        max(latency_ms) as max_ms
  by model
| sort -avg_ms
""",
    "cache_savings": """
index=mcp_agents event_type=mcp_cache_hit earliest={timerange}
| stats sum(saved_cost) as total_saved_usd,
        sum(saved_latency_ms) as total_saved_ms,
        count as cache_hits
""",
    "router_decisions": """
index=mcp_agents event_type=mcp_router_decision earliest={timerange}
| stats count by query_complexity, selected_model, strategy
| sort -count
""",
    "agent_performance": """
index=mcp_agents event_type=mcp_agent_complete earliest={timerange}
| stats avg(duration_ms) as avg_duration,
        avg(total_cost) as avg_cost,
        avg(total_tokens) as avg_tokens,
        sum(eval(if(success="True",1,0))) as success_count,
        count as total_count
| eval success_rate=round(success_count/total_count*100,2)
""",
    "anomalies": """
index=mcp_agents event_type=mcp_anomaly earliest={timerange}
| stats count by anomaly_type, model, remediation_triggered
| sort -count
""",
    "cost_trend": """
index=mcp_agents event_type=mcp_llm_call earliest={timerange}
| timechart span=1h sum(cost_usd) as hourly_cost by model
""",
    "top_users": """
index=mcp_agents earliest={timerange}
| stats sum(cost_usd) as total_cost,
        count as total_calls
  by user_id
| sort -total_cost
| head 10
""",
}

# NL 키워드 → 템플릿 매핑
NL_KEYWORD_MAP = {
    ("비용", "cost", "얼마", "지출", "spend"):    "hourly_cost",
    ("에러", "error", "실패", "fail"):             "error_rate",
    ("dlp", "보안", "violation", "위반"):          "dlp_violations",
    ("레이턴시", "latency", "느림", "slow", "응답속도"): "model_latency",
    ("캐시", "cache", "절감"):                    "cache_savings",
    ("라우터", "router", "routing", "선택"):       "router_decisions",
    ("에이전트", "agent", "성능", "performance"):  "agent_performance",
    ("이상", "anomaly", "스파이크", "spike"):      "anomalies",
    ("추세", "trend", "시간별", "hourly"):         "cost_trend",
    ("사용자", "user", "유저"):                    "top_users",
}


# ──────────────────────────────────────────────
# Splunk REST API Client
# ──────────────────────────────────────────────

class SplunkRESTClient:
    """Splunk Enterprise/Cloud REST API 클라이언트"""

    def __init__(
        self,
        base_url:  str = "",
        token:     str = "",
        username:  str = "",
        password:  str = "",
    ):
        self.base_url = base_url or os.environ.get("SPLUNK_API_URL", "https://localhost:8089")
        self.token    = token    or os.environ.get("SPLUNK_API_TOKEN", "")
        self.username = username or os.environ.get("SPLUNK_USERNAME", "admin")
        self.password = password or os.environ.get("SPLUNK_PASSWORD", "")

    def _auth_header(self) -> str:
        if self.token:
            return f"Bearer {self.token}"
        import base64
        cred = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return f"Basic {cred}"

    def run_search(self, spl: str, earliest: str = "-1h", latest: str = "now",
                   max_results: int = 100) -> Dict[str, Any]:
        """SPL 검색 실행 및 결과 반환"""
        search_url = f"{self.base_url}/services/search/jobs"
        body = (
            f"search={spl.strip()}"
            f"&earliest_time={earliest}"
            f"&latest_time={latest}"
            f"&output_mode=json"
            f"&count={max_results}"
        )
        headers = {
            "Authorization": self._auth_header(),
            "Content-Type":  "application/x-www-form-urlencoded",
        }
        try:
            req = Request(search_url, data=body.encode(), headers=headers, method="POST")
            with urlopen(req, timeout=30) as resp:
                job_data = json.loads(resp.read())
                sid = job_data.get("sid", "")
                if sid:
                    return self._poll_results(sid, headers)
        except Exception as e:
            logger.warning(f"Splunk REST error: {e}")
            return {"error": str(e), "results": []}

        return {"results": []}

    def _poll_results(self, sid: str, headers: dict, max_wait: int = 30) -> Dict:
        results_url = f"{self.base_url}/services/search/jobs/{sid}/results?output_mode=json"
        for _ in range(max_wait):
            time.sleep(1)
            try:
                req = Request(results_url, headers=headers)
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    if "results" in data:
                        return data
            except Exception:
                pass
        return {"results": [], "error": "timeout"}


# ──────────────────────────────────────────────
# Splunk MCP Tool
# ──────────────────────────────────────────────

class SplunkMCPTool:
    """
    Splunk MCP Server Tool — Tool Manager에 등록되는 커넥터

    에이전트가 자연어로 운영 데이터를 쿼리합니다.
    Splunk MCP Server (GA 2026)가 없는 환경에서는
    REST API 직접 호출로 폴백합니다.
    """

    TOOL_NAME        = "splunk_query"
    TOOL_DESCRIPTION = (
        "Query MCPAgents operational data from Splunk. "
        "Use this tool to answer questions about LLM costs, error rates, "
        "DLP violations, model performance, cache savings, and anomalies. "
        "Accepts natural language or raw SPL queries."
    )

    # MCP Server 엔드포인트 (Splunk MCP Server GA 2026)
    MCP_SERVER_URL = os.environ.get("SPLUNK_MCP_SERVER_URL", "")

    def __init__(self):
        self._rest = SplunkRESTClient()
        self._mcp_available = self._check_mcp_server()

    def _check_mcp_server(self) -> bool:
        if not self.MCP_SERVER_URL:
            return False
        try:
            req = Request(f"{self.MCP_SERVER_URL}/health",
                         headers={"Authorization": f"Bearer {os.environ.get('SPLUNK_MCP_TOKEN','')}"})
            with urlopen(req, timeout=3):
                logger.info("✅ Splunk MCP Server connected")
                return True
        except Exception:
            logger.info("Splunk MCP Server not reachable — using REST API fallback")
            return False

    def get_tool_schema(self) -> Dict:
        """MCP Tool 스키마 (Tool Manager 등록용)"""
        return {
            "name": self.TOOL_NAME,
            "description": self.TOOL_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query or raw SPL (prefixed with 'SPL:')."
                    },
                    "timerange": {
                        "type": "string",
                        "description": "Time range: -1h, -24h, -7d, -30d (default: -1h)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum rows to return (default: 50)"
                    }
                },
                "required": ["query"]
            }
        }

    def execute(
        self,
        query:       str,
        timerange:   str = "-1h",
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """
        자연어 또는 SPL 쿼리 실행

        Args:
            query:       자연어 질문 또는 "SPL: <spl>" 형식
            timerange:   시간 범위 (-1h, -24h, -7d, -30d)
            max_results: 최대 결과 수

        Returns:
            dict: { "results": [...], "spl": "...", "summary": "..." }
        """
        start = time.time()

        # 1. SPL 결정: 직접 입력 or NL → SPL 변환
        if query.upper().startswith("SPL:"):
            spl = query[4:].strip()
        else:
            spl = self._nl_to_spl(query, timerange)

        # 2. MCP Server 우선, REST API 폴백
        if self._mcp_available:
            raw = self._query_via_mcp_server(spl, timerange, max_results)
        else:
            raw = self._rest.run_search(spl, earliest=timerange, max_results=max_results)

        results = raw.get("results", [])
        elapsed = (time.time() - start) * 1000

        return {
            "results":     results,
            "result_count": len(results),
            "spl":         spl,
            "timerange":   timerange,
            "query_ms":    round(elapsed, 1),
            "source":      "mcp_server" if self._mcp_available else "rest_api",
            "summary":     self._summarize(query, results)
        }

    def _nl_to_spl(self, nl_query: str, timerange: str) -> str:
        """자연어 → SPL 변환 (키워드 매칭 기반)"""
        q = nl_query.lower()
        for keywords, template_key in NL_KEYWORD_MAP.items():
            if any(kw in q for kw in keywords):
                return SPL_TEMPLATES[template_key].format(timerange=timerange).strip()
        # 기본: 전체 이벤트 검색
        return f"index=mcp_agents earliest={timerange} | head 50"

    def _query_via_mcp_server(self, spl: str, timerange: str, max_results: int) -> Dict:
        """Splunk MCP Server를 통한 쿼리 (2026 GA API)"""
        payload = json.dumps({
            "tool": "run_search",
            "arguments": {
                "query":       spl,
                "earliest":    timerange,
                "max_results": max_results
            }
        }).encode()
        headers = {
            "Authorization": f"Bearer {os.environ.get('SPLUNK_MCP_TOKEN','')}",
            "Content-Type":  "application/json",
        }
        try:
            req = Request(f"{self.MCP_SERVER_URL}/call", data=payload, headers=headers)
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as e:
            logger.warning(f"MCP Server query failed, falling back to REST: {e}")
            self._mcp_available = False
            return self._rest.run_search(spl, earliest=timerange, max_results=max_results)

    @staticmethod
    def _summarize(query: str, results: list) -> str:
        """결과 자연어 요약"""
        if not results:
            return "No results found for the given query and time range."
        n = len(results)
        keys = list(results[0].keys()) if results else []
        return (f"Found {n} row(s). Fields: {', '.join(keys[:6])}. "
                f"Top result: {json.dumps(results[0])[:200]}")


# ── Tool Manager 등록 헬퍼 ──────────────────────

def register_splunk_tool(tool_manager) -> SplunkMCPTool:
    """
    기존 Tool Manager에 Splunk MCP Tool을 등록합니다.

    Usage:
        from tools.splunk_mcp_tool import register_splunk_tool
        from enterprise_mcp_connector.tool_manager import ToolManager

        tm = ToolManager()
        splunk_tool = register_splunk_tool(tm)
    """
    tool = SplunkMCPTool()
    schema = tool.get_tool_schema()

    # Tool Manager의 등록 방식에 맞게 래핑
    def splunk_executor(**kwargs):
        return tool.execute(**kwargs)

    if hasattr(tool_manager, "register_tool"):
        tool_manager.register_tool(
            name=schema["name"],
            description=schema["description"],
            func=splunk_executor,
            schema=schema
        )
    elif hasattr(tool_manager, "_tools"):
        tool_manager._tools[schema["name"]] = splunk_executor

    logger.info(f"✅ SplunkMCPTool registered: {schema['name']}")
    return tool


# ── 빠른 테스트 ─────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    tool = SplunkMCPTool()
    print("Schema:", json.dumps(tool.get_tool_schema(), indent=2, ensure_ascii=False))

    test_queries = [
        "지난 1시간 LLM 비용 얼마야?",
        "DLP 위반 현황 보여줘",
        "모델별 에러율 알려줘",
        "캐시 절감 효과는?",
        "SPL: index=mcp_agents | head 5",
    ]
    for q in test_queries:
        result = tool.execute(q, timerange="-1h")
        print(f"\n[{q}]")
        print(f"  SPL: {result['spl'][:80]}...")
        print(f"  Summary: {result['summary'][:100]}")
