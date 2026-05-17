"""
API auth — shared-secret X-MCP-Token guard.

Env-gated and graceful: if MCP_API_TOKEN is unset/empty the endpoints behave
exactly as before (open) so Demo Mode / local dev are unaffected. When set, a
constant-time exact match of the X-MCP-Token header is required.

Pure functions here use stdlib only (no FastAPI) so they are unit-testable
without importing the heavy app. The optional FastAPI dependency is defined
only if FastAPI is importable.
"""
import os
import hmac
import logging

logger = logging.getLogger(__name__)


def _expected_token() -> str:
    return os.getenv("MCP_API_TOKEN", "").strip()


def auth_enabled() -> bool:
    """True when an API token is configured (auth enforced)."""
    return bool(_expected_token())


def verify_api_token(provided) -> bool:
    """Return True if the request is authorized.

    - MCP_API_TOKEN unset/empty -> auth disabled, always True (open).
    - MCP_API_TOKEN set -> require exact constant-time match.
    """
    expected = _expected_token()
    if not expected:
        return True
    if not provided:
        return False
    return hmac.compare_digest(str(provided), expected)


try:  # FastAPI dependency (optional import — pure fns above stay dependency-free)
    from fastapi import Header, HTTPException

    def require_token(x_mcp_token: str = Header(default=None, alias="X-MCP-Token")):
        if not verify_api_token(x_mcp_token):
            raise HTTPException(status_code=401,
                                detail="invalid or missing X-MCP-Token")
        return True
except ImportError:  # pragma: no cover - FastAPI not installed in some envs
    require_token = None
