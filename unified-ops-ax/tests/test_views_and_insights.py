from app.agents.insights import InsightsAgent
from app.domain.models import Customer, Employee, Lead, Product
from app.domain.services import open_as_ticket, place_order, resolve_as_ticket
from app.views.inventory import inventory_status
from app.views.performance import employee_performance
from app.views.pipeline import pipeline


def test_inventory_allocation_and_availability(session):
    prod = Product(sku="P1", name="Widget", unit_price=10.0, stock_qty=10)
    cust = Customer(name="Acme")
    session.add_all([prod, cust])
    session.commit()
    place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 3}])  # status placed

    inv = {i["sku"]: i for i in inventory_status(session)}
    assert inv["P1"]["allocated"] == 3
    assert inv["P1"]["available"] == 7


def test_pipeline_conversion_rate(session):
    cust = Customer(name="Acme")
    session.add(cust)
    session.commit()
    for status in ["new", "new", "converted", "lost", "qualified"]:
        session.add(Lead(customer_id=cust.id, status=status))
    session.commit()

    pipe = pipeline(session)
    assert pipe["lead_total"] == 5
    assert pipe["converted"] == 1
    assert pipe["conversion_rate"] == 0.2


def test_employee_performance_counts_activities_and_as(session):
    cust = Customer(name="Acme")
    emp = Employee(name="Kim", role="as")
    session.add_all([cust, emp])
    session.commit()
    ticket = open_as_ticket(session, customer_id=cust.id, summary="문제 발생")
    ticket.assignee_id = emp.id
    session.commit()
    resolve_as_ticket(session, ticket.id, "해결")  # emits as.resolved with actor=assignee

    perf = {p["name"]: p for p in employee_performance(session)}
    assert perf["Kim"]["as_resolved"] == 1
    assert perf["Kim"]["activity_count"] >= 1  # as.resolved attributed to actor


def test_insights_detects_oversold_and_overload(session):
    cust = Customer(name="Acme")
    prod = Product(sku="P1", name="Widget", unit_price=10.0, stock_qty=1)
    emp = Employee(name="Lee", role="as")
    session.add_all([cust, prod, emp])
    session.commit()
    place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 3}])  # oversold: 1-3=-2
    for i in range(3):  # overload Lee with 3 open tickets
        t = open_as_ticket(session, customer_id=cust.id, summary=f"이슈{i}")
        t.assignee_id = emp.id
        t.status = "assigned"
    session.commit()

    result = InsightsAgent(session).run()
    kinds = {s["type"] for s in result["signals"]}
    assert "inventory_oversold" in kinds
    assert "overloaded_staff" in kinds
    assert result["read_only"] is True


def test_insights_clean_when_no_signals(session):
    result = InsightsAgent(session).run()
    assert result["signals"] == []
    assert "정상" in result["narrative"]
