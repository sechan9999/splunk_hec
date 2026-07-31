"""Accounting SaaS adapters (port pattern). The core talks only to
AccountingPort; swapping SaaS = swapping an adapter. The Fake adapter is an
in-memory ledger so orchestration runs and tests offline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol
from urllib.parse import quote

from app.config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ExternalTxn:
    external_id: str
    order_id: Optional[str]
    amount: float
    currency: str
    kind: str = "sale"  # sale | refund
    status: str = "posted"
    occurred_at: datetime = None  # type: ignore[assignment]


class AccountingPort(Protocol):
    name: str

    def post_transaction(self, *, order_id: str, amount: float, currency: str,
                         kind: str = "sale", memo: str | None = None) -> ExternalTxn: ...

    def list_transactions(self, since: datetime | None = None) -> list[ExternalTxn]: ...


class FakeAccountingAdapter:
    name = "fake"

    def __init__(self) -> None:
        self._ledger: dict[str, ExternalTxn] = {}
        self._seq = 0

    def post_transaction(self, *, order_id, amount, currency, kind="sale", memo=None) -> ExternalTxn:
        self._seq += 1
        txn = ExternalTxn(
            external_id=f"FAKE-TXN-{self._seq:04d}", order_id=order_id, amount=amount,
            currency=currency, kind=kind, status="posted", occurred_at=_now(),
        )
        self._ledger[txn.external_id] = txn
        return txn

    def list_transactions(self, since=None) -> list[ExternalTxn]:
        return [t for t in self._ledger.values() if since is None or t.occurred_at >= since]


class DouzoneAdapter:  # pragma: no cover - stub
    """더존 Bizbox / iCUBE. Implement post_transaction via the ERP voucher API
    (전표 등록) and list_transactions via the ledger query API. Map order_id to
    the voucher's 적요/참조번호 for reconciliation."""
    name = "douzone"

    def __init__(self, **config) -> None:
        self._config = config

    def post_transaction(self, **kwargs) -> ExternalTxn:
        raise NotImplementedError("DouzoneAdapter is a documented stub")

    def list_transactions(self, since=None) -> list[ExternalTxn]:
        raise NotImplementedError("DouzoneAdapter is a documented stub")


class QuickBooksAdapter:
    """Intuit QuickBooks Online (accounting API v3). Real REST implementation;
    testable offline via httpx.MockTransport.

      sale   -> POST /v3/company/{realm}/invoice
      refund -> POST /v3/company/{realm}/creditmemo
      list   -> GET  /v3/company/{realm}/query?query=SELECT * FROM Invoice

    Auth: OAuth2 bearer access token (user obtains via the QBO auth-code flow;
    refresh handling is the caller's responsibility). CustomerRef defaults to a
    configured value — a production deploy maps each order to a QBO customer."""
    name = "quickbooks"

    def __init__(self, *, access_token: str, realm_id: str,
                 base_url: str = "https://quickbooks.api.intuit.com",
                 default_customer_ref: str = "1", http=None) -> None:
        import httpx

        self._http = http or httpx.Client(timeout=30)
        self._base = base_url.rstrip("/")
        self._realm = realm_id
        self._token = access_token
        self._customer_ref = default_customer_ref

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json",
                "Content-Type": "application/json"}

    def _entity_url(self, entity: str) -> str:
        return f"{self._base}/v3/company/{self._realm}/{entity}?minorversion=65"

    def post_transaction(self, *, order_id, amount, currency, kind="sale", memo=None) -> ExternalTxn:
        note = memo or f"order {order_id}"
        line = [{"Amount": amount, "DetailType": "SalesItemLineDetail",
                 "SalesItemLineDetail": {"ItemRef": {"value": "1"}}}]
        payload = {"Line": line, "CustomerRef": {"value": self._customer_ref},
                   "PrivateNote": note, "CurrencyRef": {"value": currency}}
        entity = "creditmemo" if kind == "refund" else "invoice"
        resp = self._http.post(self._entity_url(entity), headers=self._headers(), json=payload)
        resp.raise_for_status()
        body = resp.json()
        obj = body.get("Invoice") or body.get("CreditMemo") or {}
        return ExternalTxn(
            external_id=str(obj.get("Id", "")), order_id=order_id,
            amount=float(obj.get("TotalAmt", amount)), currency=currency,
            kind=kind, status="posted", occurred_at=_now(),
        )

    def list_transactions(self, since=None) -> list[ExternalTxn]:
        query = "SELECT * FROM Invoice"
        resp = self._http.get(f"{self._base}/v3/company/{self._realm}/query?query={quote(query)}",
                              headers=self._headers())
        resp.raise_for_status()
        rows = resp.json().get("QueryResponse", {}).get("Invoice", [])
        out = []
        for inv in rows:
            order_id = str(inv.get("PrivateNote", "")).replace("order ", "").strip() or None
            out.append(ExternalTxn(
                external_id=str(inv.get("Id", "")), order_id=order_id,
                amount=float(inv.get("TotalAmt", 0.0)),
                currency=(inv.get("CurrencyRef") or {}).get("value", "USD"),
                kind="sale", status="posted", occurred_at=_now(),
            ))
        return out


_FAKE_SINGLETON = FakeAccountingAdapter()


def build_accounting_adapter() -> AccountingPort:
    settings = get_settings()
    provider = settings.accounting_provider
    if provider == "fake":
        return _FAKE_SINGLETON
    if provider == "douzone":
        return DouzoneAdapter()
    if provider == "quickbooks":
        if not (settings.qbo_access_token and settings.qbo_realm_id):
            raise ValueError("missing QBO_ACCESS_TOKEN / QBO_REALM_ID")
        return QuickBooksAdapter(
            access_token=settings.qbo_access_token, realm_id=settings.qbo_realm_id,
            base_url=settings.qbo_base_url, default_customer_ref=settings.qbo_customer_ref,
        )
    raise ValueError(f"unknown accounting provider: {provider}")
