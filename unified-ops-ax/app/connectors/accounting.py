"""Accounting SaaS adapters (port pattern). The core talks only to
AccountingPort; swapping SaaS = swapping an adapter. The Fake adapter is an
in-memory ledger so orchestration runs and tests offline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol

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


class QuickBooksAdapter(DouzoneAdapter):  # pragma: no cover - stub
    """Intuit QuickBooks Online. post_transaction -> POST /v3/company/{id}/invoice;
    list_transactions -> query 'SELECT * FROM Invoice'. OAuth2 auth code flow."""
    name = "quickbooks"


_FAKE_SINGLETON = FakeAccountingAdapter()


def build_accounting_adapter() -> AccountingPort:
    provider = get_settings().accounting_provider
    if provider == "fake":
        return _FAKE_SINGLETON
    if provider == "douzone":
        return DouzoneAdapter()
    if provider == "quickbooks":
        return QuickBooksAdapter()
    raise ValueError(f"unknown accounting provider: {provider}")
