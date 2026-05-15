# splunk_telemetry.py
"""
① Splunk HEC Telemetry Emitter
Splunk HTTP Event Collector 텔레메트리 에미터

MCPAgents의 모든 이벤트를 Splunk HEC로 전송합니다.
"""

import json, time, uuid, threading, queue, logging, os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)


class MCPEventType(str, Enum):
    LLM_CALL        = "mcp_llm_call"
    TOOL_CALL       = "mcp_tool_call"
    ROUTER_DECISION = "mcp_router_decision"
    DLP_VIOLATION   = "mcp_dlp_violation"
    CACHE_HIT       = "mcp_cache_hit"
    CACHE_MISS      = "mcp_cache_miss"
    AGENT_START     = "mcp_agent_start"
    AGENT_COMPLETE  = "mcp_agent_complete"
    AGENT_ERROR     = "mcp_agent_error"
    AUDIT_EVENT     = "mcp_audit_event"
    ANOMALY         = "mcp_anomaly"
    REMEDIATION     = "mcp_remediation"


@dataclass
class BaseMCPEvent:
    event_type: str
    timestamp:  str  = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    event_id:   str  = field(default_factory=lambda: str(uuid.uuid4())[:16])
    session_id: str  = ""
    user_id:    str  = ""
    app:        str  = "mcpagents"
    version:    str  = "2.0.0-splunk"

    def to_hec_payload(self, index: str = "mcp_agents") -> dict:
        return {
            "time":       time.time(),
            "host":       "mcpagents-host",
            "source":     "mcpagents:telemetry",
            "sourcetype": "mcp:agent:event",
            "index":      index,
            "event":      asdict(self)
        }


@dataclass
class LLMCallEvent(BaseMCPEvent):
    event_type:        str   = MCPEventType.LLM_CALL
    model:             str   = ""
    provider:          str   = ""
    prompt_tokens:     int   = 0
    completion_tokens: int   = 0
    total_tokens:      int   = 0
    cost_usd:          float = 0.0
    latency_ms:        float = 0.0
    success:           bool  = True
    cached:            bool  = False
    complexity:        str   = ""
    error:             str   = ""


@dataclass
class ToolCallEvent(BaseMCPEvent):
    event_type:  str   = MCPEventType.TOOL_CALL
    tool_name:   str   = ""
    tool_args:   str   = ""
    result_size: int   = 0
    latency_ms:  float = 0.0
    success:     bool  = True
    dlp_checked: bool  = False
    dlp_clean:   bool  = True
    error:       str   = ""


@dataclass
class RouterDecisionEvent(BaseMCPEvent):
    event_type:            str   = MCPEventType.ROUTER_DECISION
    query_complexity:      str   = ""
    complexity_confidence: float = 0.0
    selected_model:        str   = ""
    fallback_model:        str   = ""
    strategy:              str   = ""
    estimated_cost:        float = 0.0
    estimated_latency_ms:  int   = 0
    decision_time_ms:      float = 0.0


@dataclass
class DLPViolationEvent(BaseMCPEvent):
    event_type:       str = MCPEventType.DLP_VIOLATION
    rule_id:          str = ""
    rule_name:        str = ""
    sensitivity:      str = ""
    action_taken:     str = ""
    tool_name:        str = ""
    direction:        str = ""
    matched_patterns: int = 0
    matched_keywords: int = 0
    data_hash:        str = ""
    destination:      str = ""


@dataclass
class CacheEvent(BaseMCPEvent):
    event_type:       str   = MCPEventType.CACHE_HIT
    cache_key:        str   = ""
    model:            str   = ""
    saved_cost:       float = 0.0
    saved_latency_ms: float = 0.0


@dataclass
class AgentEvent(BaseMCPEvent):
    event_type:   str   = MCPEventType.AGENT_START
    query:        str   = ""
    tools_used:   str   = ""
    total_steps:  int   = 0
    duration_ms:  float = 0.0
    total_cost:   float = 0.0
    total_tokens: int   = 0
    success:      bool  = True
    error:        str   = ""


@dataclass
class AnomalyEvent(BaseMCPEvent):
    event_type:            str   = MCPEventType.ANOMALY
    anomaly_type:          str   = ""
    metric_name:           str   = ""
    current_value:         float = 0.0
    threshold:             float = 0.0
    model:                 str   = ""
    remediation_triggered: bool  = False


class SplunkHECClient:
    """Splunk HEC 비동기 배치 클라이언트"""

    def __init__(self, hec_url="", hec_token="", index="mcp_agents",
                 batch_size=50, flush_interval_sec=2.0):
        self.hec_url   = hec_url   or os.environ.get("SPLUNK_HEC_URL", "http://localhost:8088")
        self.hec_token = hec_token or os.environ.get("SPLUNK_HEC_TOKEN", "")
        self.index     = index
        self.batch_size = batch_size
        self.flush_interval = flush_interval_sec
        self.enabled   = bool(self.hec_token)
        self._queue: queue.Queue = queue.Queue(maxsize=10_000)
        self._sent = 0; self._dropped = 0

        if self.enabled:
            threading.Thread(target=self._flush_loop, daemon=True, name="splunk-hec").start()
            logger.info(f"Splunk HEC → {self.hec_url} (index={self.index})")
        else:
            logger.warning("Splunk HEC disabled — set SPLUNK_HEC_TOKEN to enable")

    def _flush_loop(self):
        while True:
            time.sleep(self.flush_interval)
            self._flush()

    def _flush(self):
        batch = []
        try:
            while len(batch) < self.batch_size:
                batch.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        if batch:
            self._send_batch(batch)

    def _send_batch(self, events):
        payload = "\n".join(json.dumps(e) for e in events)
        url     = f"{self.hec_url.rstrip('/')}/services/collector/event"
        headers = {"Authorization": f"Splunk {self.hec_token}",
                   "Content-Type": "application/json"}
        try:
            req = Request(url, data=payload.encode(), headers=headers, method="POST")
            with urlopen(req, timeout=5) as r:
                if r.status == 200:
                    self._sent += len(events)
        except Exception as e:
            logger.debug(f"HEC send failed: {e}")
            self._dropped += len(events)

    def enqueue(self, event: BaseMCPEvent):
        logger.debug(f"[TEL] {event.event_type} {json.dumps(asdict(event))[:150]}")
        if not self.enabled:
            return
        try:
            self._queue.put_nowait(event.to_hec_payload(self.index))
        except queue.Full:
            self._dropped += 1

    def flush_now(self):
        self._flush()

    def stats(self):
        return {"queue": self._queue.qsize(), "sent": self._sent,
                "dropped": self._dropped, "enabled": self.enabled}


class SplunkTelemetry:
    """MCPAgents Splunk 텔레메트리 파사드 (싱글톤 권장)"""

    def __init__(self, hec_client=None):
        self._hec = hec_client or SplunkHECClient()
        self._session_id = str(uuid.uuid4())[:16]
        self._user_id = ""

    def set_session(self, session_id, user_id=""):
        self._session_id = session_id
        self._user_id = user_id

    def _ctx(self):
        return {"session_id": self._session_id, "user_id": self._user_id}

    def emit_llm_call(self, model, prompt_tokens=0, completion_tokens=0,
                      cost_usd=0.0, latency_ms=0.0, success=True,
                      cached=False, complexity="", error=""):
        self._hec.enqueue(LLMCallEvent(
            model=model, provider=self._provider(model),
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=prompt_tokens+completion_tokens,
            cost_usd=cost_usd, latency_ms=latency_ms, success=success,
            cached=cached, complexity=complexity, error=error, **self._ctx()))

    def emit_tool_call(self, tool_name, tool_args=None, result_size=0,
                       latency_ms=0.0, success=True, dlp_checked=False,
                       dlp_clean=True, error=""):
        self._hec.enqueue(ToolCallEvent(
            tool_name=tool_name, tool_args=json.dumps(tool_args or {})[:256],
            result_size=result_size, latency_ms=latency_ms, success=success,
            dlp_checked=dlp_checked, dlp_clean=dlp_clean, error=error, **self._ctx()))

    def emit_router_decision(self, complexity, confidence=0.0, selected_model="",
                             fallback_model="", strategy="", estimated_cost=0.0,
                             estimated_latency=0, decision_time_ms=0.0):
        self._hec.enqueue(RouterDecisionEvent(
            query_complexity=complexity, complexity_confidence=confidence,
            selected_model=selected_model, fallback_model=fallback_model,
            strategy=strategy, estimated_cost=estimated_cost,
            estimated_latency_ms=estimated_latency, decision_time_ms=decision_time_ms,
            **self._ctx()))

    def emit_dlp_violation(self, rule_id, rule_name, sensitivity, action_taken,
                           tool_name="", direction="outbound", matched_patterns=0,
                           matched_keywords=0, data_hash="", destination=""):
        self._hec.enqueue(DLPViolationEvent(
            rule_id=rule_id, rule_name=rule_name, sensitivity=sensitivity,
            action_taken=action_taken, tool_name=tool_name, direction=direction,
            matched_patterns=matched_patterns, matched_keywords=matched_keywords,
            data_hash=data_hash, destination=destination, **self._ctx()))

    def emit_cache_hit(self, model, cache_key="", saved_cost=0.0, saved_latency_ms=0.0):
        self._hec.enqueue(CacheEvent(event_type=MCPEventType.CACHE_HIT,
            cache_key=cache_key, model=model, saved_cost=saved_cost,
            saved_latency_ms=saved_latency_ms, **self._ctx()))

    def emit_cache_miss(self, model, cache_key=""):
        self._hec.enqueue(CacheEvent(event_type=MCPEventType.CACHE_MISS,
            cache_key=cache_key, model=model, **self._ctx()))

    def emit_agent_start(self, query):
        self._hec.enqueue(AgentEvent(event_type=MCPEventType.AGENT_START,
            query=query[:200], **self._ctx()))

    def emit_agent_complete(self, query, tools_used=None, total_steps=0,
                            duration_ms=0.0, total_cost=0.0, total_tokens=0,
                            success=True, error=""):
        evt = MCPEventType.AGENT_COMPLETE if success else MCPEventType.AGENT_ERROR
        self._hec.enqueue(AgentEvent(
            event_type=evt, query=query[:200],
            tools_used=",".join(tools_used or []),
            total_steps=total_steps, duration_ms=duration_ms,
            total_cost=total_cost, total_tokens=total_tokens,
            success=success, error=error, **self._ctx()))

    def emit_anomaly(self, anomaly_type, metric_name, current_value,
                     threshold, model="", remediation_triggered=False):
        self._hec.enqueue(AnomalyEvent(
            anomaly_type=anomaly_type, metric_name=metric_name,
            current_value=current_value, threshold=threshold,
            model=model, remediation_triggered=remediation_triggered, **self._ctx()))

    @staticmethod
    def _provider(model):
        m = model.lower()
        if "claude" in m:  return "anthropic"
        if "gpt"   in m:   return "openai"
        if "gemini" in m:  return "google"
        return "unknown"

    def get_stats(self):
        return self._hec.stats()

    def flush(self):
        self._hec.flush_now()


# ── 싱글톤 ──────────────────────────────────────
_instance: Optional[SplunkTelemetry] = None
_lock = threading.Lock()

def get_telemetry() -> SplunkTelemetry:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SplunkTelemetry()
    return _instance

def init_telemetry(hec_url: str, hec_token: str, index: str = "mcp_agents") -> SplunkTelemetry:
    global _instance
    _instance = SplunkTelemetry(SplunkHECClient(hec_url=hec_url, hec_token=hec_token, index=index))
    return _instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    tel = SplunkTelemetry()
    tel.set_session("test-001", "gyver")
    tel.emit_agent_start("React hooks 사용법")
    tel.emit_router_decision("COMPLEX", 0.85, "claude-3.5-sonnet", "gpt-4o",
                             "quality_first", 0.0024, 1200, 45.2)
    tel.emit_llm_call("claude-3.5-sonnet", 350, 820, 0.0037, 1340.0, True, False, "COMPLEX")
    tel.emit_tool_call("get_docs", {"library":"react"}, 2048, 120, True, True, True)
    tel.emit_dlp_violation("DLP-001","Credit Card Detection","RESTRICTED","block","email_send")
    tel.emit_cache_hit("claude-3.5-sonnet", saved_cost=0.003, saved_latency_ms=1200)
    tel.emit_agent_complete("React hooks", ["get_docs","generate_code"], 4, 1600, 0.0037, 1170)
    tel.emit_anomaly("cost_spike","hourly_cost_usd", 8.5, 5.0, "claude-3-opus", True)
    print("Stats:", tel.get_stats())
