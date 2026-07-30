from datetime import datetime, timezone

from sqlalchemy import select

from app.connectors.calendar import ExternalEvent, FakeCalendarAdapter
from app.domain.models import ScheduleEvent
from app.orchestration.calendar import CalendarOrchestrator


def _dt(hour=9):
    return datetime(2026, 8, 1, hour, 0, tzinfo=timezone.utc)


def test_push_assigns_external_id_and_marks_synced(session):
    session.add(ScheduleEvent(title="Kickoff", start=_dt(9), end=_dt(10)))
    session.commit()
    adapter = FakeCalendarAdapter()

    assert CalendarOrchestrator(adapter).push(session) == {"pushed": 1}
    se = session.scalars(select(ScheduleEvent)).one()
    assert se.external_id and se.external_id.startswith("FAKE-EVT-")
    assert se.status == "synced"
    assert len(adapter.list_events()) == 1


def test_pull_creates_local_event_from_saas(session):
    adapter = FakeCalendarAdapter()
    adapter.upsert_event(ExternalEvent(external_id=None, title="Vendor call", start=_dt(14).isoformat()))

    assert CalendarOrchestrator(adapter).pull(session) == {"created": 1, "updated": 0}
    se = session.scalars(select(ScheduleEvent)).one()
    assert se.title == "Vendor call"
    assert se.source == "fake"
    assert se.status == "synced"


def test_round_trip_does_not_duplicate(session):
    session.add(ScheduleEvent(title="Standup", start=_dt(9)))
    session.commit()
    adapter = FakeCalendarAdapter()
    orch = CalendarOrchestrator(adapter)

    orch.push(session)                 # local -> SaaS (external_id assigned)
    result = orch.pull(session)        # SaaS -> local (should update, not create)
    assert result == {"created": 0, "updated": 1}
    assert len(session.scalars(select(ScheduleEvent)).all()) == 1
