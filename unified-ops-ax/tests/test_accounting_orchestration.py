from sqlalchemy import select

from app.connectors.accounting import FakeAccountingAdapter
from app.domain.models import Customer, Product, Transaction
from app.domain.services import place_order
from app.orchestration.accounting import AccountingOrchestrator
from app.views.customer360 import customer_360


def _seed_orders(session, n=2):
    customer = Customer(name="Acme")
    product = Product(sku="P1", name="Widget", unit_price=100.0)
    session.add_all([customer, product])
    session.commit()
    for _ in range(n):
        place_order(session, customer_id=customer.id, lines=[{"product_id": product.id, "qty": 1}])
    return customer


def test_sync_mirrors_orders_and_reconciles_clean(session):
    _seed_orders(session, 2)
    orch = AccountingOrchestrator(FakeAccountingAdapter())

    assert orch.sync_pending(session) == {"synced": 2}
    assert len(session.scalars(select(Transaction)).all()) == 2

    report = orch.reconcile(session)
    assert report["total_orders"] == 2
    assert report["matched"] == 2
    assert report["integrity_rate"] == 1.0
    assert report["healthy"] is True


def test_sync_is_idempotent(session):
    _seed_orders(session, 2)
    orch = AccountingOrchestrator(FakeAccountingAdapter())
    orch.sync_pending(session)
    assert orch.sync_pending(session) == {"synced": 0}  # no double-post
    assert len(session.scalars(select(Transaction)).all()) == 2


def test_reconcile_flags_missing_transaction(session):
    _seed_orders(session, 2)
    # never synced -> both orders missing their mirror
    report = AccountingOrchestrator(FakeAccountingAdapter()).reconcile(session)
    assert len(report["missing"]) == 2
    assert report["integrity_rate"] == 0.0
    assert report["healthy"] is False


def test_reconcile_flags_amount_mismatch(session):
    _seed_orders(session, 1)
    orch = AccountingOrchestrator(FakeAccountingAdapter())
    orch.sync_pending(session)
    txn = session.scalars(select(Transaction)).first()
    txn.amount = txn.amount + 50  # SaaS drifted from source of truth
    session.commit()

    report = orch.reconcile(session)
    assert report["matched"] == 0
    assert report["mismatched"] and report["mismatched"][0]["expected"] == 100.0
    assert report["healthy"] is False


def test_transaction_posted_appears_in_customer_360(session):
    customer = _seed_orders(session, 1)
    AccountingOrchestrator(FakeAccountingAdapter()).sync_pending(session)
    view = customer_360(session, customer.id)
    assert any(e["type"] == "transaction.posted" for e in view["timeline"])
