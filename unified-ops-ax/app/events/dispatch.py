"""Event dispatcher (outbox pattern). Closes the A4/B2 gap the right way:
the emitting transaction only writes Activity rows; this dispatcher runs
AFTERWARD, in its own transaction per event, and triggers agents. No nested
commits inside business transactions. `Activity.dispatched` makes it
idempotent and replayable — a stand-in for a real broker (Postgres NOTIFY /
Redis) that a background worker or cron would drive."""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.domain.models import Activity

logger = logging.getLogger(__name__)

# event_type -> list of (subject_type, handler(session, activity))
HANDLERS: dict[str, list[tuple[str, object]]] = {}


def register(event_type: str, subject_type: str, handler) -> None:
    HANDLERS.setdefault(event_type, []).append((subject_type, handler))


def wire_default_handlers() -> None:
    """Wire agents to events (design §4 'agents subscribe to events')."""
    from app.agents.followup import FollowUpAgent
    from app.agents.knowledge import KnowledgeCaptureAgent
    from app.agents.triage import ASTriageAgent

    HANDLERS.clear()
    register("as.opened", "as", lambda s, a: ASTriageAgent(s).run(a.subject_id))
    register("delivery.done", "order", lambda s, a: FollowUpAgent(s).draft_for_order(a.subject_id))
    register("as.resolved", "as", lambda s, a: KnowledgeCaptureAgent(s).run(a.subject_id))


def dispatch_pending(session_factory, limit: int = 200) -> dict:
    """Drain undispatched activities, triggering registered handlers. Each
    activity is marked dispatched and committed individually (fail-isolated)."""
    processed, triggered, failed = 0, 0, 0
    session = session_factory()
    try:
        pending = session.scalars(
            select(Activity).where(Activity.dispatched == False)  # noqa: E712
            .order_by(Activity.occurred_at).limit(limit)
        ).all()
        for activity in pending:
            for subject_type, handler in HANDLERS.get(activity.type, []):
                if activity.subject_type != subject_type:
                    continue  # skip duplicate anchors (e.g. as.opened on customer)
                try:
                    handler(session, activity)
                    triggered += 1
                except Exception as exc:  # fail-isolated: one bad event won't stall the queue
                    logger.warning("dispatch handler failed for %s/%s: %s", activity.type, activity.id, exc)
                    failed += 1
            activity.dispatched = True
            session.commit()
            processed += 1
    finally:
        session.close()
    return {"processed": processed, "triggered": triggered, "failed": failed}


wire_default_handlers()
