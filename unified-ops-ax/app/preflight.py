"""Preflight — validate live wiring before flipping from fake to real. Reports
each subsystem's status (fake | configured | ok | missing | error) WITHOUT
revealing secret values, so it is safe to expose. Run:
    python -m app.preflight        (CLI)   or   GET /ops/preflight
`configured` means credentials are present; a live probe is not performed
(to avoid surprise API costs) — DB connectivity is checked since it is free."""
from __future__ import annotations

from app.config import Settings, get_settings


def _check_llm(s: Settings) -> dict:
    p = s.default_llm_provider
    if p == "fake":
        return {"subsystem": "llm", "provider": p, "status": "fake"}
    has = {"anthropic": s.anthropic_api_key, "openai": s.openai_api_key,
           "onprem": s.onprem_base_url}.get(p)
    return {"subsystem": "llm", "provider": p, "status": "configured" if has else "missing"}


def _check_embeddings(s: Settings) -> dict:
    p = s.embedding_provider
    if p == "fake":
        return {"subsystem": "embeddings", "provider": p, "status": "fake"}
    ok = s.openai_api_key if p == "openai" else True
    return {"subsystem": "embeddings", "provider": p, "status": "configured" if ok else "missing"}


def _check_vector(s: Settings) -> dict:
    if s.vector_backend == "memory":
        return {"subsystem": "vector", "provider": "memory", "status": "ok"}
    return {"subsystem": "vector", "provider": s.vector_backend, "status": "configured"}


def _check_database(s: Settings) -> dict:
    provider = s.database_url.split(":", 1)[0]
    try:
        from sqlalchemy import text
        from app.db import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"subsystem": "database", "provider": provider, "status": "ok"}
    except Exception as exc:
        return {"subsystem": "database", "provider": provider, "status": "error", "detail": str(exc)[:120]}


def _check_graph(s: Settings) -> dict:
    configured = all([s.graph_tenant_id, s.graph_client_id, s.graph_client_secret])
    detail = {"sharepoint": bool(s.sharepoint_site_id), "teams": bool(s.teams_group_id),
              "calendar_mailbox": bool(s.calendar_user_id)}
    return {"subsystem": "graph", "status": "configured" if configured else "missing", "detail": detail}


def _check_saas(s: Settings) -> list[dict]:
    if s.accounting_provider == "fake":
        acc = "fake"
    elif s.accounting_provider == "quickbooks":
        acc = "configured" if (s.qbo_access_token and s.qbo_realm_id) else "missing"
    else:
        acc = "configured"
    if s.calendar_provider == "fake":
        cal = "fake"
    elif s.calendar_provider == "msgraph":
        cal = "configured" if s.calendar_user_id else "missing"
    else:
        cal = "configured"
    return [
        {"subsystem": "accounting", "provider": s.accounting_provider, "status": acc},
        {"subsystem": "calendar", "provider": s.calendar_provider, "status": cal},
    ]


def _check_pii(s: Settings) -> dict:
    return {"subsystem": "pii", "status": "configured" if s.pii_key else "plaintext"}


def preflight() -> dict:
    s = get_settings()
    checks = [_check_llm(s), _check_embeddings(s), _check_vector(s), _check_database(s),
              _check_graph(s), _check_pii(s)]
    checks += _check_saas(s)
    live = any(c.get("status") == "configured" for c in checks)
    # Only hard errors (e.g. DB unreachable) need attention. `missing` means an
    # optional integration isn't configured yet — informational, not a failure.
    errors = [c["subsystem"] for c in checks if c.get("status") == "error"]
    return {
        "mode": "live" if live else "offline-fake",
        "ready": not errors,
        "checks": checks,
        "attention": errors,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(preflight(), indent=2, ensure_ascii=False))
