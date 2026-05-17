# endpoint-auth — Gap Analysis (Check)

- **Date**: 2026-05-16
- **Feature**: endpoint-auth
- **Phase**: Check
- **Baseline**: `docs/01-plan/features/endpoint-auth.plan.md` (no separate design doc — small P0 security feature; Plan FR list used as spec)
- **Implementation**: deployed `master` = `fc2c32d`

## Match Rate: 100% (0 gaps)

All Plan requirements verified against committed code with line-level evidence.

## Requirement → Implementation Trace

| Req | Spec | Evidence | Status |
|-----|------|----------|--------|
| FR-1 | `MCP_API_TOKEN` unset/empty → open + logged | `api_auth.py:20,28-37` (`verify_api_token` True when expected empty); `main.py:79` logs `open (MCP_API_TOKEN unset)` | ✅ |
| FR-2 | set → require `X-MCP-Token`, constant-time, else 401 | `api_auth.py:39` `hmac.compare_digest`; `api_auth.py:45-48` `require_token` → `HTTPException(401)` | ✅ |
| FR-3 | Protect `/agent/run`, `/splunk/alert`, `/metrics/*` | `main.py:132` `/agent/run dependencies=_AUTH`; `main.py:97,103,108,113,117` 5×`/metrics/* dependencies=_AUTH`; `auto_remediation.py:343` `/alert dependencies=_auth` | ✅ |
| FR-4 | `/health`, `/splunk/health` always open | `main.py:121` `/health` (no dependency); `auto_remediation.py:348` `/splunk/health` (no dependency) | ✅ |
| FR-5 | demo_app non-Demo sends header; Demo unaffected | `demo_app.py:152` API Token input; `:170-171` `_auth_headers()`; `:184,193` headers on agent_run/fire_alert; `:143` Demo branch `api_token=""` → header `None` | ✅ |
| FR-6 | Pure auth logic, stdlib-only, FastAPI optional | `api_auth.py` `os`/`hmac` only; `:43-51` FastAPI in `try/except` → pure fns unit-tested without FastAPI | ✅ |
| NFR | Zero new dependency; no change when unset | stdlib `os`,`hmac`; regression smoke test passed (Demo Mode unchanged) | ✅ |

## Acceptance Criteria

| Criterion | Result |
|-----------|--------|
| token unset → `verify_api_token(None|"x")==True` | ✅ unit test [A] |
| token set → match True; mismatch/None/empty False | ✅ unit test [A] |
| constant-time compare used | ✅ `compare_digest` asserted in source |
| `py_compile` all changed files | ✅ 4 files |
| Headless all-buttons Demo Mode regression | ✅ no regression |
| Deployed to master (Streamlit auto-redeploy) | ✅ `fc2c32d` pushed |

## Gaps
None.

## Residual Risk / Notes (out of Plan scope)
- Auth is **opt-in**: until `MCP_API_TOKEN` is set on the backend host, endpoints remain open by design (graceful degradation). Operator action required to actually enforce.
- `X-MCP-Token` is a static shared secret over HTTPS — adequate for webhook/service auth; not per-user identity (explicitly out of scope per Plan).
- Pre-existing `mcpagents2026` in git history is a separate finding (tracked elsewhere) — unrelated to this feature.

## Verdict
Check ≥ 90% (100%) → proceed to `/pdca report endpoint-auth`. No `iterate` needed.
