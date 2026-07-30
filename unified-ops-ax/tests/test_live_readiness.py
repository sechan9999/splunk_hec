"""Live-readiness: preflight reports correct statuses in fake mode, and the
MS Graph calendar adapter works over real Graph HTTP shapes (MockTransport)."""
import json

import httpx

from app.connectors.calendar import ExternalEvent, MSGraphCalendarAdapter
from app.connectors.graph_client import GraphAuth, GraphClient
from app.preflight import preflight


# --- preflight (offline/fake) -----------------------------------------------
def test_preflight_reports_fake_mode(session):
    report = preflight()
    by = {c["subsystem"]: c for c in report["checks"]}
    assert report["mode"] == "offline-fake"
    assert report["ready"] is True  # sqlite connects, nothing errored
    assert by["llm"]["status"] == "fake"
    assert by["database"]["status"] == "ok"
    assert by["graph"]["status"] == "missing"      # no creds by default
    assert by["accounting"]["status"] == "fake"


# --- MS Graph calendar adapter (live shapes via MockTransport) --------------
def _adapter():
    store: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        path, method = request.url.path, request.method
        if method == "POST" and path == "/v1.0/users/u1/events":
            body = json.loads(request.content)
            ev = {"id": "EVT1", "subject": body["subject"], "start": body["start"],
                  "end": body.get("end"), "lastModifiedDateTime": "2026-08-01T00:00:00Z"}
            store["EVT1"] = ev
            return httpx.Response(201, json=ev)
        if method == "GET" and path == "/v1.0/users/u1/events":
            return httpx.Response(200, json={"value": list(store.values())})
        if method == "PATCH" and path.startswith("/v1.0/users/u1/events/"):
            eid = path.rsplit("/", 1)[1]
            store[eid]["subject"] = json.loads(request.content)["subject"]
            return httpx.Response(200, json=store[eid])
        if method == "DELETE" and path.startswith("/v1.0/users/u1/events/"):
            store.pop(path.rsplit("/", 1)[1], None)
            return httpx.Response(204)
        return httpx.Response(404, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    auth = GraphAuth("t", "c", "s", login_base_url="https://login.microsoftonline.com", http=http)
    return MSGraphCalendarAdapter(GraphClient(auth, base_url="https://graph.microsoft.com/v1.0", http=http), "u1")


def test_msgraph_calendar_crud():
    adapter = _adapter()
    created = adapter.upsert_event(ExternalEvent(external_id=None, title="Kickoff", start="2026-08-01T09:00:00Z"))
    assert created.external_id == "EVT1"
    assert [e.external_id for e in adapter.list_events()] == ["EVT1"]

    updated = adapter.upsert_event(ExternalEvent(external_id="EVT1", title="Kickoff v2", start="2026-08-01T09:00:00Z"))
    assert updated.title == "Kickoff v2"

    adapter.delete_event("EVT1")
    assert adapter.list_events() == []
