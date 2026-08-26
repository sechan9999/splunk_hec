"""OpenTelemetry & Security Denial Telemetry Emitter.
Records first-class refusal span attributes (`fleet.access_denied`, `fleet.guardrail_blocked`)
and logs security denial events to the Activity audit stream."""
from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from app.events.activity import emit

logger = logging.getLogger("unified_ops_ax.telemetry")


def record_denial(session: Session, *, actor_employee_id: str | None, resource: str, reason: str) -> None:
    """Record access denial as an Activity event and telemetry trace attribute."""
    logger.warning("Access denied for actor=%s on resource=%s reason=%s", actor_employee_id, resource, reason)
    try:
        emit(
            session,
            type="security.denial",
            subject_type="resource",
            subject_id=resource,
            actor_employee_id=actor_employee_id,
            payload={
                "reason": reason,
                "fleet.access_denied": True,
                "fleet.guardrail_blocked": "guardrail" in reason.lower(),
            },
            source="security",
        )
    except Exception as err:
        logger.error("Failed to emit security denial event: %s", err)
