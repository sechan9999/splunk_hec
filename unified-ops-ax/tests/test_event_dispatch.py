"""Event dispatcher (outbox) — agents fire from events, not manual calls,
and each event is processed exactly once."""
from sqlalchemy import select

from app.db import SessionLocal
from app.domain.models import ASTicket, Customer, Employee, FollowUp, KnowledgeItem, Product
from app.domain.services import mark_delivered, open_as_ticket, place_order, resolve_as_ticket
from app.events.dispatch import dispatch_pending


def test_as_opened_auto_triggers_triage(session):
    cust = Customer(name="Acme")
    emp = Employee(name="Park", role="production")
    session.add_all([cust, emp])
    session.commit()
    ticket_id = open_as_ticket(session, customer_id=cust.id, summary="전원 부품 고장").id

    result = dispatch_pending(SessionLocal)
    assert result["triggered"] >= 1

    session.expire_all()
    ticket = session.get(ASTicket, ticket_id)
    assert ticket.category == "hardware"
    assert ticket.assignee_id == emp.id
    assert ticket.status == "assigned"


def test_delivery_done_auto_triggers_followup_draft(session):
    cust = Customer(name="Acme")
    prod = Product(sku="P1", name="Widget", unit_price=100.0)
    session.add_all([cust, prod])
    session.commit()
    order = place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 1}])
    mark_delivered(session, order.id)

    dispatch_pending(SessionLocal)
    session.expire_all()
    drafts = session.scalars(select(FollowUp).where(FollowUp.status == "draft")).all()
    assert len(drafts) == 1


def test_as_resolved_auto_triggers_knowledge(session):
    cust = Customer(name="Acme")
    session.add(cust)
    session.commit()
    ticket = open_as_ticket(session, customer_id=cust.id, summary="용지 걸림 오류")
    resolve_as_ticket(session, ticket.id, "롤러 청소")

    dispatch_pending(SessionLocal)
    session.expire_all()
    assert len(session.scalars(select(KnowledgeItem)).all()) >= 1


def test_dispatch_is_idempotent(session):
    cust = Customer(name="Acme")
    emp = Employee(name="Park", role="production")
    session.add_all([cust, emp])
    session.commit()
    open_as_ticket(session, customer_id=cust.id, summary="전원 고장")

    dispatch_pending(SessionLocal)
    second = dispatch_pending(SessionLocal)
    assert second["triggered"] == 0  # nothing new fires on replay
