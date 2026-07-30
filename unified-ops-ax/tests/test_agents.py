from sqlalchemy import select

from app.agents.followup import FollowUpAgent
from app.agents.knowledge import KnowledgeCaptureAgent
from app.agents.rules import classify
from app.agents.triage import ASTriageAgent
from app.domain.models import Activity, ASTicket, Customer, Employee, FollowUp, KnowledgeItem, Product
from app.domain.services import mark_delivered, open_as_ticket, place_order, resolve_as_ticket
from app.rag.service import retrieve
from app.security.rbac import principals_for


# --- rules (unit) -----------------------------------------------------------
def test_classify_category_and_severity():
    assert classify("제품 전원이 안 들어와요 부품 고장")[0] == "hardware"
    assert classify("환불 요청합니다")[0] == "billing"
    assert classify("배송이 아직 도착 안 함")[0] == "delivery"
    assert classify("서버 전체 다운 긴급")[1] == "high"
    assert classify("사용법 문의드립니다")[1] == "low"


# --- triage -----------------------------------------------------------------
def test_triage_routes_to_role_and_records_event(session):
    cust = Customer(name="Acme")
    prod = Employee(name="Park", role="production")
    session.add_all([cust, prod])
    session.commit()
    ticket = open_as_ticket(session, customer_id=cust.id, summary="전원 고장 부품 교체 필요")

    result = ASTriageAgent(session).run(ticket.id)
    assert result["category"] == "hardware"
    assert result["assignee_id"] == prod.id
    reloaded = session.get(ASTicket, ticket.id)
    assert reloaded.status == "assigned"
    types = {a.type: a.source for a in session.scalars(select(Activity)).all()}
    assert types.get("as.triaged") == "agent"


def test_triage_picks_least_loaded_owner(session):
    cust = Customer(name="Acme")
    p1 = Employee(name="Kim", role="production")
    p2 = Employee(name="Lee", role="production")
    session.add_all([cust, p1, p2])
    session.commit()
    # p1 already has an open ticket
    busy = open_as_ticket(session, customer_id=cust.id, summary="기존 고장 건")
    busy.assignee_id = p1.id
    busy.status = "assigned"
    session.commit()

    new_ticket = open_as_ticket(session, customer_id=cust.id, summary="전원 부품 고장")
    result = ASTriageAgent(session).run(new_ticket.id)
    assert result["assignee_id"] == p2.id  # least loaded


def test_triage_unassigned_when_no_owner_role(session):
    cust = Customer(name="Acme")
    session.add(cust)
    session.commit()
    ticket = open_as_ticket(session, customer_id=cust.id, summary="환불 요청")  # billing -> accounting (none exist)
    result = ASTriageAgent(session).run(ticket.id)
    assert result["assignee_id"] is None
    assert session.get(ASTicket, ticket.id).status == "open"


# --- knowledge capture ------------------------------------------------------
def test_knowledge_capture_creates_draft_and_is_retrievable(session):
    cust = Customer(name="Acme")
    session.add(cust)
    session.commit()
    ticket = open_as_ticket(session, customer_id=cust.id, summary="프린터 용지 걸림 오류 발생")
    ASTriageAgent(session).run(ticket.id)
    resolve_as_ticket(session, ticket.id, "롤러 청소 후 정상 작동 확인")

    result = KnowledgeCaptureAgent(session).run(ticket.id)
    item = session.get(KnowledgeItem, result["knowledge_id"])
    assert item.status == "draft"
    assert "software" in item.tags
    # closed loop: the captured knowledge is retrievable via RAG
    hits = retrieve("용지 걸림 오류", principals_for("sales"), k=5)
    assert any("용지" in h.text for h in hits)
    assert any(a.type == "knowledge.captured" and a.source == "agent"
               for a in session.scalars(select(Activity)).all())


# --- follow-up (HITL) -------------------------------------------------------
def test_followup_drafts_but_does_not_send(session):
    cust = Customer(name="Acme")
    prod = Product(sku="P1", name="Widget", unit_price=100.0)
    session.add_all([cust, prod])
    session.commit()
    order = place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 1}])
    mark_delivered(session, order.id)

    result = FollowUpAgent(session).draft_for_order(order.id)
    assert result["status"] == "draft"
    assert result["requires_approval"] is True
    assert result["draft"]
    # the agent must NOT have sent anything
    sent = [a for a in session.scalars(select(Activity)).all() if a.type == "followup.sent"]
    assert sent == []


def test_followup_send_requires_human_approval(session):
    cust = Customer(name="Acme")
    prod = Product(sku="P1", name="Widget", unit_price=100.0)
    session.add_all([cust, prod])
    session.commit()
    order = place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 1}])
    agent = FollowUpAgent(session)
    fu_id = agent.draft_for_order(order.id)["followup_id"]

    sent = agent.approve_and_send(fu_id)  # human gate
    assert sent["status"] == "sent"
    assert session.get(FollowUp, fu_id).status == "sent"
    assert any(a.type == "followup.sent" and a.source == "app"
               for a in session.scalars(select(Activity)).all())
    # idempotent
    assert agent.approve_and_send(fu_id).get("already") is True
