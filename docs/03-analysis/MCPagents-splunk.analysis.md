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

## Match Rate: 100% (Act iteration 1 complete — all gaps closed)

9 integration assertions verified. Iteration 1 (2026-05-15): gaps #2–4 resolved.
History: 88% (Check) → 100% (Act-1).

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
| 2 | Minor | demo_app.py:356 (Tab4 SOAR) | `resp.get("result",{}).get("tool_results",[])` assumed dict; same crash class as #1. | ✅ FIXED (isinstance guard) |
| 3 | Minor | demo_app.py:173 | Agent-failed-but-HTTP-200 (`success:False`) not surfaced. | ✅ FIXED (`success is False` check) |
| 4 | Minor/UX | demo_app.py:301 (Tab3) | Cooldown `{skipped:True}` mislabeled "handled=False". | ✅ FIXED (skipped/error/reason branches) |
| 5 | Info | demo_app.py:131–132 | `telemetry.get_stats()` keys `sent`/`dropped` assumed; safe via `.get(...,0)` defaults. No action needed. | ✓ OK |

## Matched (no gap)

- `/health` → `remediation.remediator.{remediation_count, active_cooldowns}` ✓
- `/agent/run` HTTP-failure path → `{error}` → error surfaced ✓
- `/splunk/alert` handled path → `anomaly_value, threshold, actions[{action,result}], cooldown_sec` ✓
- `/splunk/alert` below-threshold → `{handled:False, reason}` ✓

## Resolution (Act iteration 1, 2026-05-15)

1. ✅ demo_app.py:356 — `isinstance(res_obj, dict)` guard (mirrors line 181).
2. ✅ demo_app.py:173 — `failed = result.get("success") is False or (...)`.
3. ✅ demo_app.py:301–315 — Tab3 branches: handled / skipped(cooldown) / error / reason.

All gaps closed. `python -m py_compile demo_app.py` passes. Match rate 100% → ready for `/pdca report`.
