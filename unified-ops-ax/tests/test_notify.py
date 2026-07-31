"""Notifier adapters + the HITL-gated follow-up delivery."""
import httpx
from sqlalchemy import select

from app.agents.followup import FollowUpAgent
from app.connectors.notify import FakeNotifier, TwilioNotifier
from app.domain.models import Activity, Customer, Product
from app.domain.services import mark_delivered, place_order


# --- adapters ---------------------------------------------------------------
def test_fake_notifier_records_outbox():
    n = FakeNotifier()
    res = n.send(to="a@e.com", body="hi", subject="s")
    assert res.message_id.startswith("FAKE-MSG-")
    assert n.outbox[0]["to"] == "a@e.com"


def test_twilio_notifier_sends_sms():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/2010-04-01/Accounts/AC1/Messages.json"
        assert b"Body=hi" in request.content
        return httpx.Response(201, json={"sid": "SM123", "status": "queued"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = TwilioNotifier("AC1", "tok", "+15550000000", http=http)
    res = adapter.send(to="+15551234567", body="hi")
    assert res.message_id == "SM123"
    assert res.channel == "sms"


# --- HITL delivery ----------------------------------------------------------
def _delivered_order(session):
    cust = Customer(name="Acme", email="ceo@acme.com")  # PII no-op without key in tests
    prod = Product(sku="P1", name="Widget", unit_price=100.0)
    session.add_all([cust, prod])
    session.commit()
    order = place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 1}])
    mark_delivered(session, order.id)
    return order


def test_approval_delivers_via_notifier(session):
    order = _delivered_order(session)
    notifier = FakeNotifier()
    agent = FollowUpAgent(session, notifier=notifier)
    fu_id = agent.draft_for_order(order.id)["followup_id"]

    # no send happened at draft time
    assert notifier.outbox == []

    result = agent.approve_and_send(fu_id)          # human gate
    assert result["status"] == "sent"
    assert result["delivered"] is True
    assert notifier.outbox and notifier.outbox[0]["to"] == "ceo@acme.com"
    sent = [a for a in session.scalars(select(Activity)).all() if a.type == "followup.sent"]
    assert sent and sent[0].payload["delivered"] is True


def test_approval_without_contact_marks_sent_undelivered(session):
    cust = Customer(name="NoContact")  # no email/phone
    prod = Product(sku="P2", name="Gadget", unit_price=10.0)
    session.add_all([cust, prod])
    session.commit()
    order = place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 1}])
    notifier = FakeNotifier()
    agent = FollowUpAgent(session, notifier=notifier)
    fu_id = agent.draft_for_order(order.id)["followup_id"]

    result = agent.approve_and_send(fu_id)
    assert result["status"] == "sent"
    assert result["delivered"] is False
    assert notifier.outbox == []                    # nothing to deliver to
