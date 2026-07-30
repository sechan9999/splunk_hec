"""Audit trail — read-only query over the immutable Activity stream. The
event store IS the audit log (who/what/when), so governance needs no separate
logging: it just filters and reads."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Activity


def audit_trail(
    session: Session,
    *,
    type: str | None = None,
    actor_employee_id: str | None = None,
    subject_type: str | None = None,
    source: str | None = None,
    since_days: int | None = None,
    limit: int = 100,
) -> list[dict]:
    query = select(Activity).order_by(Activity.occurred_at.desc())
    if type:
        query = query.where(Activity.type == type)
    if actor_employee_id:
        query = query.where(Activity.actor_employee_id == actor_employee_id)
    if subject_type:
        query = query.where(Activity.subject_type == subject_type)
    if source:
        query = query.where(Activity.source == source)
    if since_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        query = query.where(Activity.occurred_at >= cutoff)

    rows = session.scalars(query.limit(limit)).all()
    return [
        {
            "id": a.id,
            "type": a.type,
            "actor_employee_id": a.actor_employee_id,
            "subject_type": a.subject_type,
            "subject_id": a.subject_id,
            "source": a.source,
            "occurred_at": a.occurred_at.isoformat(),
        }
        for a in rows
    ]
