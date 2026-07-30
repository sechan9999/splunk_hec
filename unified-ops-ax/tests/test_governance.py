import pytest
from fastapi import HTTPException

from app.domain.models import Customer, Employee, Product
from app.domain.services import open_as_ticket, place_order, resolve_as_ticket
from app.governance.adoption import adoption_metrics
from app.governance.audit import audit_trail
from app.governance.dashboard import governance_dashboard
from app.governance.ownership import coverage, list_owners, set_owner
from app.security.auth import Identity, issue_token, require_manager


def _seed(session):
    cust = Customer(name="Acme")
    prod = Product(sku="P1", name="Widget", unit_price=100.0)
    emp = Employee(name="Kim", role="as")
    session.add_all([cust, prod, emp])
    session.commit()
    place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 1}])
    t = open_as_ticket(session, customer_id=cust.id, summary="문제")
    t.assignee_id = emp.id
    session.commit()
    resolve_as_ticket(session, t.id, "해결")
    return cust, emp


def test_audit_trail_reads_and_filters(session):
    _seed(session)
    all_rows = audit_trail(session, limit=100)
    assert any(r["type"] == "order.placed" for r in all_rows)
    only_as = audit_trail(session, subject_type="as")
    assert only_as and all(r["subject_type"] == "as" for r in only_as)


def test_adoption_metrics_shape(session):
    _seed(session)
    m = adoption_metrics(session)
    assert m["employees"]["total"] == 1
    assert m["knowledge_coverage"]["resolved_tickets"] == 1
    assert m["knowledge_coverage"]["knowledge_items"] == 0  # knowledge agent not run here
    assert 0.0 <= m["accounting_integrity"] <= 1.0
    assert "by_source" in m["activity"]


def test_ownership_registry(session):
    _, emp = _seed(session)
    set_owner(session, domain="crm", owner_employee_id=emp.id, classification="confidential", notes="CRM 오너")
    owners = {o["domain"]: o for o in list_owners(session)}
    assert owners["crm"]["owner_employee_id"] == emp.id
    cov = coverage(session)
    assert "crm" in cov["assigned"]
    assert "accounting" in cov["unassigned"]


def test_dashboard_aggregates(session):
    _seed(session)
    d = governance_dashboard(session)
    assert set(d) == {"adoption", "ownership", "recent_audit", "security_posture"}
    assert d["security_posture"]["security_trimming"].startswith("enabled")


def test_require_manager_blocks_non_manager():
    non_mgr = Identity("e1", "Kim", "as", {"grp:all", "grp:as"})
    with pytest.raises(HTTPException) as exc:
        require_manager(non_mgr)
    assert exc.value.status_code == 403
    mgr = Identity("e2", "Boss", "manager", {"grp:all"})
    assert require_manager(mgr) is mgr  # manager passes
