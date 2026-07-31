import httpx
from datetime import datetime, timezone
from app.connectors.accounting import DouzoneAdapter, ExternalTxn
from app.connectors.calendar import GoogleCalendarAdapter, ExternalEvent


def test_douzone_adapter_post_and_list():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/api/v1/voucher/insert" in url:
            return httpx.Response(200, json={"result": {"voucher_no": "DZ-2026-99"}})
        if "/api/v1/voucher/list" in url:
            return httpx.Response(200, json={
                "vouchers": [
                    {"voucher_no": "DZ-2026-99", "order_id": "ORD-100", "amount": 550000.0, "currency": "KRW", "voucher_type": "sales"}
                ]
            })
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = DouzoneAdapter(api_key="TEST_KEY", company_code="1000", http=client)

    txn = adapter.post_transaction(order_id="ORD-100", amount=550000.0, currency="KRW", kind="sale")
    assert txn.external_id == "DZ-2026-99"
    assert txn.order_id == "ORD-100"
    assert txn.amount == 550000.0

    items = adapter.list_transactions()
    assert len(items) == 1
    assert items[0].external_id == "DZ-2026-99"


def test_google_calendar_adapter_crud():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and "/events" in url:
            return httpx.Response(200, json={"id": "GCAL-EVT-001", "summary": "Exec Sync", "start": {"dateTime": "2026-08-01T10:00:00Z"}})
        if request.method == "PATCH" and "/events/GCAL-EVT-001" in url:
            return httpx.Response(200, json={"id": "GCAL-EVT-001", "summary": "Exec Sync Updated", "start": {"dateTime": "2026-08-01T11:00:00Z"}})
        if request.method == "GET" and "/events" in url:
            return httpx.Response(200, json={"items": [{"id": "GCAL-EVT-001", "summary": "Exec Sync Updated", "start": {"dateTime": "2026-08-01T11:00:00Z"}}]})
        if request.method == "DELETE" and "/events/GCAL-EVT-001" in url:
            return httpx.Response(204)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = GoogleCalendarAdapter(access_token="G_TEST_TOKEN", calendar_id="primary", http=client)

    evt = adapter.upsert_event(ExternalEvent(external_id=None, title="Exec Sync", start="2026-08-01T10:00:00Z"))
    assert evt.external_id == "GCAL-EVT-001"

    updated = adapter.upsert_event(ExternalEvent(external_id="GCAL-EVT-001", title="Exec Sync Updated", start="2026-08-01T11:00:00Z"))
    assert updated.title == "Exec Sync Updated"

    events = adapter.list_events()
    assert len(events) == 1
    assert events[0].title == "Exec Sync Updated"

    adapter.delete_event("GCAL-EVT-001")
