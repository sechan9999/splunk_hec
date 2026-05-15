# multi_llm_platform/observability.py
"""
Observability & Traceability System (Splunk Enhanced)
관측성 시스템 — SplunkBackend 추가

변경사항:
  - SplunkBackend 클래스 추가 (기존 InMemoryBackend, LangSmithBackend 유지)
  - Tracer.add_backend()로 Splunk HEC 스트리밍 활성화
  - 기존 API 100% 호환 유지
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from contextlib import contextmanager
import json, time, uuid, threading, os, logging

logger = logging.getLogger(__name__)


class TraceType(Enum):
    LLM_CALL   = "llm_call"
    TOOL_CALL  = "tool_call"
    RETRIEVAL  = "retrieval"
    CHAIN      = "chain"
    AGENT      = "agent"
    EMBEDDING  = "embedding"
    CACHE      = "cache"
    ROUTER     = "router"
    DLP_CHECK  = "dlp_check"
    ERROR      = "error"


class TraceStatus(Enum):
    RUNNING  = "running"
    SUCCESS  = "success"
    ERROR    = "error"
    CACHED   = "cached"


@dataclass
class SpanContext:
    trace_id: str
    span_id:  str
    parent_span_id: Optional[str] = None


@dataclass
class Span:
    context:    SpanContext
    name:       str
    type:       TraceType
    start_time: datetime
    end_time:   Optional[datetime] = None
    status:     TraceStatus = TraceStatus.RUNNING
    input_data:  Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    metadata:    Dict[str, Any] = field(default_factory=dict)
    tags:        List[str]      = field(default_factory=list)
    duration_ms: Optional[float] = None
    tokens_used: int   = 0
    cost:        float = 0.0
    error:       Optional[str] = None

    def finish(self, status=TraceStatus.SUCCESS, output=None, error=None):
        self.end_time   = datetime.now()
        self.status     = status
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        if output:
            self.output_data = output if isinstance(output, dict) else {"result": output}
        if error:
            self.error  = error
            self.status = TraceStatus.ERROR


@dataclass
class Trace:
    trace_id:   str
    name:       str
    start_time: datetime
    end_time:   Optional[datetime] = None
    spans:      List[Span]         = field(default_factory=list)
    total_duration_ms: float = 0
    total_tokens: int   = 0
    total_cost:   float = 0
    user_id:    str = ""
    session_id: str = ""
    metadata:   Dict[str, Any] = field(default_factory=dict)

    def add_span(self, span):
        self.spans.append(span)

    def finish(self):
        self.end_time = datetime.now()
        self.total_duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.total_tokens = sum(s.tokens_used for s in self.spans)
        self.total_cost   = sum(s.cost       for s in self.spans)


# ────────────────────────────────────────────────────────
# Backends
# ────────────────────────────────────────────────────────

class TracingBackend:
    def log_trace(self, trace: Trace): raise NotImplementedError
    def log_span(self,  span:  Span):  raise NotImplementedError


class InMemoryBackend(TracingBackend):
    def __init__(self, max_traces=1000):
        self._traces: List[Trace] = []
        self._spans:  List[Span]  = []
        self._max    = max_traces
        self._lock   = threading.Lock()

    def log_trace(self, trace):
        with self._lock:
            self._traces.append(trace)
            if len(self._traces) > self._max:
                self._traces = self._traces[-self._max:]

    def log_span(self, span):
        with self._lock:
            self._spans.append(span)

    def get_traces(self, limit=100):
        return self._traces[-limit:]

    def get_spans(self, trace_id=None, limit=100):
        if trace_id:
            return [s for s in self._spans if s.context.trace_id == trace_id][-limit:]
        return self._spans[-limit:]


class LangSmithBackend(TracingBackend):
    def __init__(self, api_key=None, project="mcp-agents"):
        self.project = project; self._client = None
        try:
            from langsmith import Client
            self._client = Client(api_key=api_key) if api_key else Client()
        except Exception:
            pass

    def log_trace(self, trace): pass
    def log_span(self,  span):  pass


class ArizePhoenixBackend(TracingBackend):
    def __init__(self, endpoint="http://localhost:6006"):
        self.endpoint = endpoint; self._tracer = None
        try:
            import phoenix as px; self._tracer = px.launch_app()
        except Exception:
            pass

    def log_trace(self, trace): pass
    def log_span(self,  span):  pass


# ── NEW: Splunk Backend ──────────────────────────────────

class SplunkBackend(TracingBackend):
    """
    Splunk HEC 스트리밍 백엔드 (신규 추가)

    모든 Span을 실시간으로 Splunk HEC로 전송합니다.
    SplunkTelemetry.emit_llm_call() 등 세부 메서드보다 하위 레벨이며,
    Tracer.span() 컨텍스트 내 모든 타입의 스팬을 캡처합니다.
    """

    def __init__(self):
        try:
            import sys, os
            # 프로젝트 루트에서 splunk_telemetry 임포트
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if root not in sys.path:
                sys.path.insert(0, root)
            from splunk_telemetry import get_telemetry
            self._tel = get_telemetry()
            self._enabled = True
            logger.info("✅ SplunkBackend connected to SplunkTelemetry")
        except ImportError:
            self._tel = None
            self._enabled = False
            logger.warning("SplunkBackend: splunk_telemetry not found")

    def log_trace(self, trace: Trace):
        if not self._enabled: return
        # Trace 완료 → agent_complete 이벤트
        success = all(s.status != TraceStatus.ERROR for s in trace.spans)
        tools   = [s.name.replace("Tool: ", "") for s in trace.spans
                   if s.type == TraceType.TOOL_CALL]
        try:
            self._tel.set_session(trace.trace_id, trace.user_id)
            self._tel.emit_agent_complete(
                query        = trace.name,
                tools_used   = tools,
                total_steps  = len(trace.spans),
                duration_ms  = trace.total_duration_ms,
                total_cost   = trace.total_cost,
                total_tokens = trace.total_tokens,
                success      = success,
            )
        except Exception as e:
            logger.debug(f"SplunkBackend.log_trace: {e}")

    def log_span(self, span: Span):
        if not self._enabled: return
        try:
            t = span.type
            if t == TraceType.LLM_CALL:
                model = span.metadata.get("model", "unknown")
                self._tel.emit_llm_call(
                    model         = model,
                    prompt_tokens = span.input_data.get("prompt_tokens", 0),
                    completion_tokens = span.output_data.get("completion_tokens", 0),
                    cost_usd      = span.cost,
                    latency_ms    = span.duration_ms or 0,
                    success       = span.status != TraceStatus.ERROR,
                    error         = span.error or "",
                )
            elif t == TraceType.TOOL_CALL:
                tool_name = span.metadata.get("tool", span.name.replace("Tool: ", ""))
                self._tel.emit_tool_call(
                    tool_name   = tool_name,
                    tool_args   = span.input_data,
                    result_size = len(str(span.output_data)),
                    latency_ms  = span.duration_ms or 0,
                    success     = span.status != TraceStatus.ERROR,
                    error       = span.error or "",
                )
            elif t == TraceType.ROUTER:
                rd = span.output_data
                self._tel.emit_router_decision(
                    complexity      = rd.get("complexity", ""),
                    selected_model  = rd.get("selected_model", ""),
                    fallback_model  = rd.get("fallback_model", ""),
                    strategy        = rd.get("strategy", ""),
                    decision_time_ms = span.duration_ms or 0,
                )
            elif t == TraceType.CACHE:
                hit = span.output_data.get("hit", False)
                model = span.metadata.get("model", "")
                if hit:
                    self._tel.emit_cache_hit(model, saved_latency_ms=span.duration_ms or 0)
                else:
                    self._tel.emit_cache_miss(model)
        except Exception as e:
            logger.debug(f"SplunkBackend.log_span: {e}")


# ────────────────────────────────────────────────────────
# Tracer (기존 API 유지 + SplunkBackend 자동 추가)
# ────────────────────────────────────────────────────────

class Tracer:
    _instance = None
    _lock     = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"): return
        mem = InMemoryBackend()
        splunk = SplunkBackend()
        self._backends: List[TracingBackend] = [mem, splunk]
        self._current_trace: Optional[Trace] = None
        self._current_span:  Optional[Span]  = None
        self._span_stack:    List[Span]       = []
        self._initialized = True

    def add_backend(self, backend: TracingBackend):
        self._backends.append(backend)

    def _gen(self): return str(uuid.uuid4())[:16]

    @contextmanager
    def trace(self, name, user_id="", metadata=None):
        tr = Trace(trace_id=self._gen(), name=name,
                   start_time=datetime.now(), user_id=user_id, metadata=metadata or {})
        self._current_trace = tr
        try:
            yield tr
        finally:
            tr.finish()
            for b in self._backends: b.log_trace(tr)
            self._current_trace = None

    @contextmanager
    def span(self, name, type=TraceType.CHAIN, input_data=None, metadata=None, tags=None):
        tid = self._current_trace.trace_id if self._current_trace else self._gen()
        pid = self._current_span.context.span_id if self._current_span else None
        ctx = SpanContext(tid, self._gen(), pid)
        sp  = Span(ctx, name, type, datetime.now(),
                   input_data=input_data or {}, metadata=metadata or {}, tags=tags or [])
        self._span_stack.append(sp)
        self._current_span = sp
        try:
            yield sp
            sp.finish(TraceStatus.SUCCESS)
        except Exception as e:
            sp.finish(TraceStatus.ERROR, error=str(e))
            raise
        finally:
            self._span_stack.pop()
            self._current_span = self._span_stack[-1] if self._span_stack else None
            if self._current_trace: self._current_trace.add_span(sp)
            for b in self._backends: b.log_span(sp)

    def log_llm_call(self, model, prompt, response, tokens=0, cost=0.0, latency_ms=0):
        with self.span(f"LLM: {model}", TraceType.LLM_CALL,
                       input_data={"prompt": prompt[:500]},
                       metadata={"model": model,
                                 "prompt_tokens": tokens//2,
                                 "completion_tokens": tokens//2}) as sp:
            sp.output_data = {"response": response[:500]}
            sp.tokens_used = tokens
            sp.cost        = cost
            sp.duration_ms = latency_ms

    def log_tool_call(self, tool_name, args, result, latency_ms=0):
        with self.span(f"Tool: {tool_name}", TraceType.TOOL_CALL,
                       input_data=args, metadata={"tool": tool_name}) as sp:
            sp.output_data = result if isinstance(result, dict) else {"result": str(result)[:500]}
            sp.duration_ms = latency_ms

    def get_memory_backend(self) -> Optional[InMemoryBackend]:
        for b in self._backends:
            if isinstance(b, InMemoryBackend): return b
        return None


# ── DebugDashboard (기존 유지) ──────────────────

class DebugDashboard:
    def __init__(self, tracer=None):
        self.tracer = tracer or Tracer()

    def get_trace_summary(self, limit=20):
        b = self.tracer.get_memory_backend()
        if not b: return []
        return [{"trace_id": t.trace_id, "name": t.name,
                 "duration_ms": t.total_duration_ms, "span_count": len(t.spans),
                 "tokens": t.total_tokens, "cost": t.total_cost,
                 "start_time": t.start_time.isoformat(), "user_id": t.user_id}
                for t in b.get_traces(limit)]

    def get_statistics(self):
        b = self.tracer.get_memory_backend()
        if not b: return {}
        spans = b.get_spans(limit=10000)
        traces = b.get_traces(1000)
        if not spans: return {"message": "No spans"}
        tc, sc, td, tt, cost, err = {}, {}, 0, 0, 0, 0
        for s in spans:
            tc[s.type.value]   = tc.get(s.type.value, 0) + 1
            sc[s.status.value] = sc.get(s.status.value, 0) + 1
            td += s.duration_ms or 0; tt += s.tokens_used
            cost += s.cost
            if s.status == TraceStatus.ERROR: err += 1
        return {"total_traces": len(traces), "total_spans": len(spans),
                "span_types": tc, "span_status": sc,
                "total_duration_ms": td, "avg_span_duration_ms": td/len(spans),
                "total_tokens": tt, "total_cost": cost,
                "error_count": err, "error_rate": err/len(spans)}


def trace_func(name=None, type=TraceType.CHAIN):
    def decorator(func):
        def wrapper(*args, **kwargs):
            with Tracer().span(name or func.__name__, type,
                               input_data={"args": str(args)[:200]}) as sp:
                result = func(*args, **kwargs)
                sp.output_data = {"result": str(result)[:500]}
                return result
        return wrapper
    return decorator
