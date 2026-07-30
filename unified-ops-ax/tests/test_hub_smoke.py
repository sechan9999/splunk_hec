from app.domain.models import Activity, Customer, Product, ProductionJob
from app.domain.services import place_order
from app.views.customer360 import customer_360


def test_order_flow_emits_events_and_creates_job(session):
    customer = Customer(name="Acme Mfg")
    product = Product(sku="SKU-1", name="Widget", unit_price=100.0)
    session.add_all([customer, product])
    session.commit()

    order = place_order(session, customer_id=customer.id, lines=[{"product_id": product.id, "qty": 3}])

    assert order.total_amount == 300.0
    # production job auto-created (handoff automation)
    job = session.query(ProductionJob).filter_by(order_id=order.id).one()
    assert job.status == "queued"
    # events emitted for order, customer-anchored, and production
    types = {a.type for a in session.query(Activity).all()}
    assert {"order.placed", "production.queued"} <= types


def test_customer_360_assembles_journey(session):
    customer = Customer(name="Beta Co", segment="B2B")
    product = Product(sku="SKU-2", name="Gadget", unit_price=50.0)
    session.add_all([customer, product])
    session.commit()
    place_order(session, customer_id=customer.id, lines=[{"product_id": product.id, "qty": 2}])

    view = customer_360(session, customer.id)
    assert view["kpi"]["orders"] == 1
    assert view["kpi"]["lifetime_value"] == 100.0
    assert any(e["type"] == "order.placed" for e in view["timeline"])
