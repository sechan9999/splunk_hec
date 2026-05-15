# MCPagents-splunk — Gap Analysis (Check)

- **Date**: 2026-05-15
- **Feature**: MCPagents-splunk (umbrella)
- **Phase**: Check
- **Scope**: `demo_app.py` (Streamlit demo, commit 086f71f) ↔ backend API contract
  (`main.py`, `advanced_agent.py`, `auto_remediation.py`)
- **Note**: No `MCPagents-splunk.design.md` exists. The 4 component features
  (splunk-auto-remediation, splunk-hec-emitter, splunk-mcp-tool, splunk-soar-brigde)
  are already analyzed & archived at 96–100%. This analysis is a **contract-consistency
  check** of the only un-analyzed, recently changed code: the demo app.

## Match Rate: 88% (Check < 90% → iterate recommended)

9 integration assertions verified; 1 critical crash fixed, 3 minor non-crash gaps remain.

## Backend Contract (source of truth)

| Endpoint | Response shape |
|----------|----------------|
| `GET /health` | `{status, version, telemetry:{...}, remediation:{remediator:{remediation_count, active_cooldowns{}}}}` |
| `POST /agent/run` | `{success:bool, result:Any, steps:int(count), duration_ms}` — `result` (synth path) = `{query, timestamp, tool_results:[{tool,result}], summary}` |
| `POST /splunk/alert` | handled: `{handled:True, model, anomaly_type, anomaly_value, threshold, actions:[{action,result}], cooldown_sec}` · below-threshold: `{handled:False, reason}` · cooldown: `{skipped:True, reason}` |

## Gap List

| # | Severity | Location | Gap | Status |
|---|----------|----------|-----|--------|
| 1 | Critical | demo_app.py:179 | Read int `steps` count as iterable → `TypeError: 'int' object is not iterable`. Real list is `result.result.tool_results`. | ✅ FIXED |
| 2 | Minor | demo_app.py:348 (Tab4 SOAR) | `resp.get("result",{}).get("tool_results",[])` assumes `result` is a dict; `resp.result` is typed `Any`. Same crash class as #1 if a tool returns a non-dict `result`. No `isinstance` guard. | ⚠ Open |
| 3 | Minor | demo_app.py:173 | Agent-failed-but-HTTP-200 (`success:False`, no top-level `error`) not surfaced — only `"error" in result` is checked; failure falls through to empty tool render. | ⚠ Open |
| 4 | Minor/UX | demo_app.py:299–308 (Tab3) | Cooldown response `{skipped:True, reason}` has no `handled` key → rendered as misleading "handled=False — {dict}". Cooldown reason not shown clearly. | ⚠ Open |
| 5 | Info | demo_app.py:131–132 | `telemetry.get_stats()` keys `sent`/`dropped` assumed; safe via `.get(...,0)` defaults. No action needed. | ✓ OK |

## Matched (no gap)

- `/health` → `remediation.remediator.{remediation_count, active_cooldowns}` ✓
- `/agent/run` HTTP-failure path → `{error}` → error surfaced ✓
- `/splunk/alert` handled path → `anomaly_value, threshold, actions[{action,result}], cooldown_sec` ✓
- `/splunk/alert` below-threshold → `{handled:False, reason}` ✓

## Recommendations

1. Apply defensive `isinstance(res_obj, dict)` guard at demo_app.py:348 (mirror the line 179 fix).
2. Surface `success:False` in Tab1 (check `result.get("success") is False`).
3. Tab3: detect `resp.get("skipped")` and show the cooldown `reason` distinctly.

Items 1–3 are small, non-architectural → `/pdca iterate MCPagents-splunk` (or apply inline) to reach ≥90%.
