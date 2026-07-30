"""Calendar SaaS adapters (port pattern). Two-way sync flows through
CalendarPort. The Fake adapter is an in-memory calendar for offline runs."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional, Protocol

from app.config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ExternalEvent:
    external_id: Optional[str]
    title: str
    start: str  # ISO 8601
    end: Optional[str] = None
    updated_at: Optional[str] = None


class CalendarPort(Protocol):
    name: str

    def upsert_event(self, event: ExternalEvent) -> ExternalEvent: ...

    def list_events(self, since: datetime | None = None) -> list[ExternalEvent]: ...

    def delete_event(self, external_id: str) -> None: ...


class FakeCalendarAdapter:
    name = "fake"

    def __init__(self) -> None:
        self._events: dict[str, ExternalEvent] = {}
        self._seq = 0

    def upsert_event(self, event: ExternalEvent) -> ExternalEvent:
        external_id = event.external_id
        if not external_id:
            self._seq += 1
            external_id = f"FAKE-EVT-{self._seq:04d}"
        stored = replace(event, external_id=external_id, updated_at=event.updated_at or _now().isoformat())
        self._events[external_id] = stored
        return stored

    def list_events(self, since=None) -> list[ExternalEvent]:
        return list(self._events.values())

    def delete_event(self, external_id: str) -> None:
        self._events.pop(external_id, None)


class MSGraphCalendarAdapter:  # pragma: no cover - live-only
    """Microsoft 365 calendar via Graph. Reuses GraphClient.
      upsert: POST/PATCH /users/{uid}/events  (subject, start, end)
      list:   GET /users/{uid}/calendarView?startDateTime=..&endDateTime=..
      delete: DELETE /users/{uid}/events/{id}
    Requires Calendars.ReadWrite application permission."""
    name = "msgraph"

    def __init__(self, client, user_id: str) -> None:
        self.client = client
        self.user_id = user_id

    def upsert_event(self, event: ExternalEvent) -> ExternalEvent:
        raise NotImplementedError("MSGraphCalendarAdapter: wire GraphClient POST/PATCH /users/{uid}/events")

    def list_events(self, since=None) -> list[ExternalEvent]:
        raise NotImplementedError("MSGraphCalendarAdapter: wire GraphClient calendarView")

    def delete_event(self, external_id: str) -> None:
        raise NotImplementedError


class GoogleCalendarAdapter:  # pragma: no cover - stub
    """Google Calendar API v3. upsert -> events.insert/patch,
    list -> events.list(updatedMin=..), delete -> events.delete. OAuth2 service
    account with domain-wide delegation."""
    name = "google"

    def __init__(self, **config) -> None:
        self._config = config

    def upsert_event(self, event: ExternalEvent) -> ExternalEvent:
        raise NotImplementedError("GoogleCalendarAdapter is a documented stub")

    def list_events(self, since=None) -> list[ExternalEvent]:
        raise NotImplementedError("GoogleCalendarAdapter is a documented stub")

    def delete_event(self, external_id: str) -> None:
        raise NotImplementedError


_FAKE_SINGLETON = FakeCalendarAdapter()


def build_calendar_adapter() -> CalendarPort:
    provider = get_settings().calendar_provider
    if provider == "fake":
        return _FAKE_SINGLETON
    if provider == "google":
        return GoogleCalendarAdapter()
    raise ValueError(f"unknown/unconfigured calendar provider: {provider}")
