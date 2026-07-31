"""QuickBooks Online adapter over real API shapes (MockTransport) + the
refund/cancel flow that keeps reconciliation integrity."""
import json

import httpx
from sqlalchemy import select

from app.connectors.accounting import FakeAccountingAdapter, QuickBooksAdapter
from app.domain.models import Customer, Product, Transaction
from app.domain.services import cancel_order, place_order
from app.orchestration.accounting import AccountingOrchestrator


# --- QuickBooks adapter -----------------------------------------------------
def _qbo():
    def handler(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if method == "POST" and path == "/v3/company/R1/invoice":
            body = json.loads(request.content)
            return httpx.Response(200, json={"Invoice": {"Id": "1042", "TotalAmt": body["Line"][0]["Amount"],
                                                         "PrivateNote": body["PrivateNote"]}})
        if method == "POST" and path == "/v3/company/R1/creditmemo":
            body = json.loads(request.content)
            return httpx.Response(200, json={"CreditMemo": {"Id": "CM7", "TotalAmt": body["Line"][0]["Amount"]}})
        if method == "GET" and path == "/v3/company/R1/query":
            return httpx.Response(200, json={"QueryResponse": {"Invoice": [
                {"Id": "1042", "TotalAmt": 300.0, "PrivateNote": "order abc",
                 "CurrencyRef": {"value": "USD"}}]}})
        return httpx.Response(404, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return QuickBooksAdapter(access_token="tok", realm_id="R1", base_url="https://qb.test", http=http)


def test_quickbooks_posts_invoice():
    txn = _qbo().post_transaction(order_id="abc", amount=300.0, currency="USD")
    assert txn.external_id == "1042"
    assert txn.amount == 300.0
    assert txn.kind == "sale"


def test_quickbooks_refund_uses_creditmemo():
    txn = _qbo().post_transaction(order_id="abc", amount=50.0, currency="USD", kind="refund")
    assert txn.external_id == "CM7"
    assert txn.kind == "refund"


def test_quickbooks_lists_invoices():
    rows = _qbo().list_transactions()
    assert rows[0].external_id == "1042"
    assert rows[0].order_id == "abc"
    assert rows[0].currency == "USD"


# --- refund / cancel flow (integrity preserved) -----------------------------
def _seed_order(session, amount=100.0):
    cust = Customer(name="Acme")
    prod = Product(sku="P1", name="Widget", unit_price=amount)
    session.add_all([cust, prod])
    session.commit()
    return place_order(session, customer_id=cust.id, lines=[{"product_id": prod.id, "qty": 1}])


def test_cancel_and_refund_nets_to_zero_and_reconciles(session):
    order = _seed_order(session, 100.0)
    orch = AccountingOrchestrator(FakeAccountingAdapter())
    orch.sync_pending(session)                      # sale 100 mirrored
    assert orch.reconcile(session)["integrity_rate"] == 1.0

    cancel_order(session, order.id)                 # order -> cancelled
    orch.post_refund(session, order.id)             # refund 100

    report = orch.reconcile(session)
    assert report["integrity_rate"] == 1.0          # expected 0 == sale - refund
    assert report["healthy"] is True
    kinds = {t.kind for t in session.scalars(select(Transaction)).all()}
    assert kinds == {"sale", "refund"}


def test_cancel_before_sync_skips_sale(session):
    order = _seed_order(session, 100.0)
    cancel_order(session, order.id)
    orch = AccountingOrchestrator(FakeAccountingAdapter())
    assert orch.sync_pending(session) == {"synced": 0}   # no sale for cancelled order
    # cancelled order with no voucher is consistent (expected 0)
    assert orch.reconcile(session)["integrity_rate"] == 1.0
