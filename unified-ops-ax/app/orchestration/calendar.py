"""Calendar orchestration — two-way sync between local ScheduleEvent rows and
a calendar SaaS. push(): local -> SaaS (assigns external_id). pull(): SaaS ->
local (upsert by external_id). Conflict policy: last-write-wins by updated_at."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.calendar import CalendarPort, ExternalEvent
from app.domain.models import ScheduleEvent


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class CalendarOrchestrator:
    def __init__(self, port: CalendarPort) -> None:
        self.port = port

    def push(self, session: Session) -> dict:
        pushed = 0
        for se in session.scalars(select(ScheduleEvent)).all():
            result = self.port.upsert_event(ExternalEvent(
                external_id=se.external_id,
                title=se.title,
                start=se.start.isoformat(),
                end=se.end.isoformat() if se.end else None,
                updated_at=se.updated_at.isoformat() if se.updated_at else None,
            ))
            se.external_id = result.external_id
            se.status = "synced"
            se.last_synced_at = _now()
            pushed += 1
        session.commit()
        return {"pushed": pushed}

    def pull(self, session: Session) -> dict:
        created, updated = 0, 0
        for ev in self.port.list_events():
            se = session.scalar(select(ScheduleEvent).where(ScheduleEvent.external_id == ev.external_id))
            if se is None:
                session.add(ScheduleEvent(
                    title=ev.title, start=_parse(ev.start), end=_parse(ev.end),
                    external_id=ev.external_id, source=self.port.name,
                    status="synced", last_synced_at=_now(),
                ))
                created += 1
            else:
                se.title = ev.title
                se.start = _parse(ev.start)
                se.end = _parse(ev.end)
                se.status = "synced"
                se.last_synced_at = _now()
                updated += 1
        session.commit()
        return {"created": created, "updated": updated}
