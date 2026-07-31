from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.accounting import build_accounting_adapter
from app.connectors.calendar import build_calendar_adapter
from app.db import get_session
from app.domain.models import ScheduleEvent
from app.domain.schemas import ScheduleEventIn
from app.orchestration.accounting import AccountingOrchestrator
from app.orchestration.calendar import CalendarOrchestrator

router = APIRouter(prefix="/ops", tags=["orchestration"])


@router.post("/accounting/sync")
def accounting_sync(session: Session = Depends(get_session)):
    return AccountingOrchestrator(build_accounting_adapter()).sync_pending(session)


@router.get("/accounting/reconcile")
def accounting_reconcile(session: Session = Depends(get_session)):
    return AccountingOrchestrator(build_accounting_adapter()).reconcile(session)


@router.post("/accounting/refund/{order_id}")
def accounting_refund(order_id: str, amount: float | None = None, session: Session = Depends(get_session)):
    return AccountingOrchestrator(build_accounting_adapter()).post_refund(session, order_id, amount)


@router.post("/schedule")
def create_schedule_event(body: ScheduleEventIn, session: Session = Depends(get_session)):
    event = ScheduleEvent(**body.model_dump())
    session.add(event)
    session.commit()
    return {"id": event.id, "title": event.title, "status": event.status}


@router.get("/schedule")
def list_schedule_events(session: Session = Depends(get_session)):
    events = session.scalars(select(ScheduleEvent)).all()
    return [
        {"id": e.id, "title": e.title, "start": e.start.isoformat(),
         "external_id": e.external_id, "status": e.status, "source": e.source}
        for e in events
    ]


@router.post("/calendar/push")
def calendar_push(session: Session = Depends(get_session)):
    return CalendarOrchestrator(build_calendar_adapter()).push(session)


@router.post("/calendar/pull")
def calendar_pull(session: Session = Depends(get_session)):
    return CalendarOrchestrator(build_calendar_adapter()).pull(session)


@router.get("/preflight")
def preflight_check():
    """Validate live wiring (safe: statuses only, no secrets)."""
    from app.preflight import preflight

    return preflight()


@router.post("/dispatch")
def dispatch_events():
    """Manually drain the event outbox once — triggers subscribed agents
    (as.opened->triage, delivery.done->followup, as.resolved->knowledge).
    In deployment the event worker drives this automatically."""
    from app.db import SessionLocal
    from app.events.dispatch import dispatch_pending

    return dispatch_pending(SessionLocal)


@router.get("/worker/status")
def worker_status():
    from app.config import get_settings
    from app.worker import get_worker

    worker = get_worker()
    return {"enabled": get_settings().event_worker_enabled, "running": worker.running, "stats": worker.stats}
