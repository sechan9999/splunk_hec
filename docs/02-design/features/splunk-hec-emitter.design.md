# Design: splunk-hec-emitter

- **Phase**: Design
- **Created**: 2026-05-15
- **Ref**: `docs/01-plan/features/splunk-hec-emitter.plan.md`

---

## Architecture Overview

```
AdvancedMCPAgent.execute()          LLMRouter.route()           SemanticCache.get/set()
        │                                  │                              │
        ▼                                  ▼                              ▼
  emit_agent_start()             emit_router_decision()         emit_cache_hit/miss()
  emit_agent_complete()          emit_llm_call()
  emit_agent_error()
        │                                  │                              │
        └──────────────────────────────────┴──────────────────────────────┘
                                           │
                                   SplunkTelemetry (singleton)
                                           │
                                   SplunkHECClient
                                    ├─ queue (10,000 max)
                                    ├─ batch flush (50 events / 2s)
                                    └─ POST /services/collector/event
                                           │
                                    Splunk HEC :8088
                                           │
                                    index=mcp_agents
```

---

## Component Design

### 1. SplunkHECClient (splunk_telemetry.py — 구현 완료)

변경 없음. 현재 구현 그대로 사용.

| 속성 | 값 |
|------|-----|
| 배치 크기 | 50 events |
| 플러시 주기 | 2초 |
| 큐 최대 | 10,000 |
| 타임아웃 | 5초 |
| 재시도 | 없음 (dropped 카운터로 추적) |
| HEC URL | `SPLUNK_HEC_URL` env (기본: `http://localhost:8088`) |
| 인증 | `Authorization: Splunk {token}` |

### 2. Hook Insertion Points (변경 대상 파일 3개)

#### 2-A. advanced_agent.py — `AdvancedMCPAgent.execute()` (line 244)

**Before (현재)**:
```python
async def execute(self, query: str, context: AgentContext = None) -> AgentResponse:
    start_time = time.time()
    steps = []
    if context is None:
        context = AgentContext(...)
    try:
        step1 = await self._analyze_query(query)
        ...
        return AgentResponse(success=True, ...)
    except Exception as e:
        return AgentResponse(success=False, ...)
```

**After (훅 삽입)**:
```python
async def execute(self, query: str, context: AgentContext = None) -> AgentResponse:
    from splunk_telemetry import get_telemetry   # 지연 임포트
    tel = get_telemetry()
    start_time = time.time()
    steps = []
    if context is None:
        context = AgentContext(...)

    tel.set_session(context.session_id, context.user_id)
    tel.emit_agent_start(query)                           # ← 추가

    try:
        ...
        duration = (time.time() - start_time) * 1000
        tel.emit_agent_complete(                          # ← 추가
            query,
            tools_used=selected_tools,
            total_steps=len(steps),
            duration_ms=duration,
            success=True
        )
        return AgentResponse(success=True, ...)
    except Exception as e:
        tel.emit_agent_complete(                          # ← 추가 (error path)
            query, success=False,
            error=str(e),
            duration_ms=(time.time() - start_time) * 1000
        )
        return AgentResponse(success=False, ...)
```

**수정 위치**: `advanced_agent.py:244–306`
**임포트**: 지연 임포트 (순환 참조 방지)

---

#### 2-B. multi_llm_platform/llm_router.py — `LLMRouter.route()` 또는 `select_model()`

`select_model()` 반환 직후 + 실제 LLM 호출 완료 후 emit.

```python
def select_model(self, prompt, complexity=None, strategy=None) -> str:
    from splunk_telemetry import get_telemetry
    t0 = time.time()
    ...
    selected = sorted_models[0]
    get_telemetry().emit_router_decision(           # ← 추가
        complexity=complexity.value,
        confidence=0.85,
        selected_model=selected,
        fallback_model=sorted_models[1] if len(sorted_models) > 1 else "",
        strategy=(strategy or self.strategy).value,
        decision_time_ms=(time.time() - t0) * 1000
    )
    return selected
```

LLM 실제 호출 래퍼 (route() 또는 generate()에서):
```python
get_telemetry().emit_llm_call(
    model=selected_model,
    prompt_tokens=usage.prompt_tokens,
    completion_tokens=usage.completion_tokens,
    cost_usd=cost,
    latency_ms=elapsed_ms,
    success=True,
    cached=False,
    complexity=complexity.value
)
```

**수정 위치**: `multi_llm_platform/llm_router.py:132–200` (select_model), 실제 호출부

---

#### 2-C. multi_llm_platform/semantic_cache.py — `SemanticCache.get()` / `set()`

```python
def get(self, query: str, model: str = "") -> Optional[Any]:
    from splunk_telemetry import get_telemetry
    result = self._lookup(query)
    if result is not None:
        get_telemetry().emit_cache_hit(model, cache_key=self._key(query),  # ← 추가
                                       saved_cost=result.metadata.get("cost", 0))
        return result.response
    get_telemetry().emit_cache_miss(model, cache_key=self._key(query))    # ← 추가
    return None
```

**수정 위치**: `multi_llm_platform/semantic_cache.py` — `get()` 메서드

---

### 3. Environment & Infrastructure (변경 없음)

`docker-compose.yml`은 이미 완성:

| 항목 | 상태 |
|------|------|
| HEC 포트 8088 노출 | ✅ `"8088:8088"` |
| `splunk-setup` 서비스 | ✅ HEC 토큰 + 인덱스 자동 생성 |
| `mcp_agents` 인덱스 | ✅ `splunk_app/default/indexes.conf` |
| MCPAgents → Splunk 내부 URL | ✅ `http://splunk:8088` |

**주의**: `splunk-setup`이 생성하는 HEC 토큰은 Splunk REST API가 반환하지만,
컨테이너 로그에서 직접 확인하거나 Splunk Web(localhost:8000)에서 복사해야 함.

토큰 확인 명령:
```powershell
docker logs mcpagents-splunk-setup
# 또는
# Splunk Web → Settings → Data Inputs → HTTP Event Collector → mcpagents_hec → Token Value
```

---

## Data Flow

```
1. 사용자 쿼리 입력
        ↓
2. AdvancedMCPAgent.execute()
   └─ emit_agent_start(query)
        ↓
3. LLMRouter.select_model()
   └─ emit_router_decision(complexity, selected_model, ...)
        ↓
4. SemanticCache.get()
   ├─ [HIT]  emit_cache_hit(model, saved_cost)  → 5번 스킵
   └─ [MISS] emit_cache_miss(model)
        ↓ (miss only)
5. 실제 LLM API 호출
   └─ emit_llm_call(model, tokens, cost, latency, success)
        ↓
6. 결과 반환
   └─ emit_agent_complete(query, tools, steps, duration, cost)
        ↓
7. SplunkHECClient 배치 플러시 (2초마다)
   └─ POST http://localhost:8088/services/collector/event
        ↓
8. Splunk index=mcp_agents
```

---

## Splunk Index Schema

`sourcetype = mcp:agent:event` 공통 필드:

| 필드 | 타입 | 예시 |
|------|------|------|
| `event_type` | string | `mcp_llm_call` |
| `timestamp` | ISO8601 | `2026-05-15T12:00:00Z` |
| `event_id` | string | `a1b2c3d4` |
| `session_id` | string | `sess_001` |
| `user_id` | string | `gyver` |
| `app` | string | `mcpagents` |

`mcp_llm_call` 추가 필드:

| 필드 | 타입 |
|------|------|
| `model` | string |
| `provider` | string |
| `prompt_tokens` | int |
| `completion_tokens` | int |
| `cost_usd` | float |
| `latency_ms` | float |
| `success` | bool |
| `cached` | bool |
| `complexity` | string |

---

## Verification SPL Queries

```spl
# 기본 이벤트 확인
index=mcp_agents | head 20

# 이벤트 타입별 카운트
index=mcp_agents | stats count by event_type

# 시간별 LLM 비용
index=mcp_agents event_type=mcp_llm_call
| timechart span=1m sum(cost_usd) as total_cost by model

# 라우터 결정 분포
index=mcp_agents event_type=mcp_router_decision
| stats count by query_complexity, selected_model

# 캐시 효율
index=mcp_agents event_type IN (mcp_cache_hit, mcp_cache_miss)
| stats count by event_type
| eval hit_rate=round(count/(sum(count) over ())*100, 1)
```

---

## Implementation Checklist

- [ ] `advanced_agent.py` — `execute()` 훅 삽입 (start/complete/error)
- [ ] `multi_llm_platform/llm_router.py` — `select_model()` + LLM 호출 emit
- [ ] `multi_llm_platform/semantic_cache.py` — `get()` cache hit/miss emit
- [ ] HEC 토큰 `.env` 설정 확인
- [ ] `python splunk_telemetry.py` 단독 테스트 (stats.sent > 0)
- [ ] `python main.py` 통합 테스트 후 SPL 쿼리 검증
