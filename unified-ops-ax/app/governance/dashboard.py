"""Governance dashboard — one view over adoption, ownership, audit, and
security posture. Manager-facing (P5)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.governance.adoption import adoption_metrics
from app.governance.audit import audit_trail
from app.governance.ownership import coverage, list_owners


def governance_dashboard(session: Session) -> dict:
    return {
        "adoption": adoption_metrics(session),
        "ownership": {"registry": list_owners(session), "coverage": coverage(session)},
        "recent_audit": audit_trail(session, limit=20),
        "security_posture": {
            "rbac": "enabled (role -> principals)",
            "security_trimming": "enabled (ACL ∩ principals before top-k)",
            "audit_log": "immutable Activity stream",
            "auth": "bearer token, role derived server-side",
            "ai_safety": "agents draft-only; external sends HITL-gated",
        },
    }
