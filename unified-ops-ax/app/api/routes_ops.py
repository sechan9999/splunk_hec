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


@router.post("/dispatch")
def dispatch_events():
    """Drain the event outbox — triggers subscribed agents (as.opened->triage,
    delivery.done->followup, as.resolved->knowledge). A worker/cron drives this."""
    from app.db import SessionLocal
    from app.events.dispatch import dispatch_pending

    return dispatch_pending(SessionLocal)
