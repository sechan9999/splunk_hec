"""Central event emitter. Every domain write should emit an Activity so that
performance, 360 views, and (future) event-bus subscribers stay consistent."""
from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.domain.models import Activity

# In-process subscribers (event bus stub). Prod: swap for Postgres NOTIFY / Redis.
_subscribers: list[Callable[[Activity], None]] = []


def subscribe(handler: Callable[[Activity], None]) -> None:
    _subscribers.append(handler)


def emit(
    session: Session,
    *,
    type: str,
    subject_type: str,
    subject_id: str,
    actor_employee_id: str | None = None,
    payload: dict | None = None,
    source: str = "app",
) -> Activity:
    activity = Activity(
        type=type,
        subject_type=subject_type,
        subject_id=subject_id,
        actor_employee_id=actor_employee_id,
        payload=payload or {},
        source=source,
    )
    session.add(activity)
    session.flush()
    for handler in _subscribers:
        handler(activity)
    return activity
