# Plan — endpoint-auth

- **Feature**: endpoint-auth
- **Date**: 2026-05-16
- **Phase**: Plan
- **Priority**: P0 (security track)

## Problem
FastAPI backend exposes `/agent/run`, `/splunk/alert`, `/metrics/*` with **no
authentication** (`main.py`, `auto_remediation.py`). `/splunk/alert` mutates
`IntelligentRouter` weights → anyone who can reach it can manipulate ops.

## Goal
Shared-secret auth (`X-MCP-Token` header) on sensitive endpoints, **env-gated and
gracefully open when unset** (Demo Mode / local dev unaffected; original behavior
preserved when no token configured — consistent with project's graceful-degradation
principle).

## Requirements
- FR-1: `MCP_API_TOKEN` env unset/empty → endpoints behave as today (open). Logged.
- FR-2: `MCP_API_TOKEN` set → protected endpoints require `X-MCP-Token` exactly
  matching, validated in constant time (`hmac.compare_digest`). Else `401`.
- FR-3: Protected: `POST /agent/run`, `POST /splunk/alert`, `GET /metrics/*`.
- FR-4: Open (always): `GET /health`, `GET /splunk/health` (uptime probes).
- FR-5: `demo_app.py` non-Demo path sends `X-MCP-Token` when an API Token is entered;
  Demo Mode unaffected (no backend calls).
- FR-6: Pure auth logic isolated in `security/api_auth.py` (stdlib only) so it is
  unit-testable without importing FastAPI / heavy deps.
- NFR: zero new runtime dependency; no change to original functionality when token unset.

## Scope
- New: `security/api_auth.py` (`verify_api_token`, `auth_enabled`, `require_token` dep).
- Edit: `main.py` (Depends on protected routes), `auto_remediation.py` (`/alert` dep),
  `demo_app.py` (optional API Token field + header), `.env.example` (`MCP_API_TOKEN`).

## Acceptance Criteria
- token unset → `verify_api_token(None|"x") == True` (open).
- token set → match `True`; mismatch/`None` `False`; constant-time compare used.
- `python -m py_compile` passes for all changed files.
- Headless all-buttons Demo Mode smoke test still passes (no regression).
- Deployed to `master` (Streamlit auto-redeploy); Demo Mode behavior unchanged.

## Out of Scope
- OAuth/JWT, per-user identity, rate limiting, git-history secret scrub.
