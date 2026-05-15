#!/usr/bin/env python3
"""
MCPAgents Splunk Modular Input
splunk-app-examples/modularinputs/python 패턴 기반

MCPAgents REST API에서 메트릭을 주기적으로 폴링하여
Splunk 인덱스에 스트리밍합니다.

Usage in inputs.conf:
  [mcp_agents://default]
  mcpagents_url = http://localhost:8000
  interval = 30
  index = mcp_agents
"""

import sys
import json
import time
import os
from urllib.request import urlopen, Request

# NOTE: splunklib must be in bin/ — see splunk-app-examples README
try:
    from splunklib.modularinput import Script, Scheme, Argument, Event, EventWriter
    SPLUNKLIB_AVAILABLE = True
except ImportError:
    SPLUNKLIB_AVAILABLE = False


class MCPAgentsInputScript:
    """MCPAgents Modular Input — Splunk SDK 기반"""

    def get_scheme(self):
        scheme = Scheme("MCPAgents AI Ops Input")
        scheme.description = "Streams MCPAgents operational metrics into Splunk"
        scheme.use_external_validation = False
        scheme.use_single_instance = False

        url_arg = Argument("mcpagents_url")
        url_arg.title = "MCPAgents API URL"
        url_arg.description = "Base URL of MCPAgents API (e.g. http://localhost:8000)"
        url_arg.required_on_create = True
        scheme.add_argument(url_arg)

        token_arg = Argument("api_token")
        token_arg.title = "API Token"
        token_arg.description = "MCPAgents API authentication token (optional)"
        token_arg.required_on_create = False
        scheme.add_argument(token_arg)

        return scheme

    def stream_events(self, inputs, ew: "EventWriter"):
        for input_name, input_item in inputs.inputs.items():
            base_url  = input_item.get("mcpagents_url", "http://localhost:8000")
            api_token = input_item.get("api_token", "")

            endpoints = [
                ("/metrics/llm",    "mcp_llm_metrics"),
                ("/metrics/router", "mcp_router_metrics"),
                ("/metrics/cache",  "mcp_cache_metrics"),
                ("/metrics/dlp",    "mcp_dlp_metrics"),
                ("/metrics/cost",   "mcp_cost_metrics"),
            ]

            for path, sourcetype in endpoints:
                data = self._fetch(f"{base_url}{path}", api_token)
                if data:
                    for record in (data if isinstance(data, list) else [data]):
                        ev = Event()
                        ev.stanza     = input_name
                        ev.sourceType = sourcetype
                        ev.data       = json.dumps(record)
                        ew.write_event(ev)

    @staticmethod
    def _fetch(url: str, token: str = "") -> any:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            sys.stderr.write(f"MCPAgents fetch error [{url}]: {e}\n")
            return None


if SPLUNKLIB_AVAILABLE:
    class MCPAgentsScript(MCPAgentsInputScript, Script):
        pass

    if __name__ == "__main__":
        sys.exit(MCPAgentsScript().run(sys.argv))
else:
    if __name__ == "__main__":
        # splunklib 없는 환경에서 직접 실행 테스트
        print("splunklib not available — running in test mode")
        inp = MCPAgentsInputScript()
        data = inp._fetch("http://localhost:8000/metrics/llm")
        print(json.dumps(data, indent=2) if data else "No data (MCPAgents not running)")
