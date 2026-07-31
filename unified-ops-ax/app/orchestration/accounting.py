"""Accounting orchestration — an idempotent outbox that pushes each order to
the accounting SaaS and mirrors the voucher back, plus a reconciliation pass.
The Activity stream (`order.placed`) is the source of truth; reconciliation
measures how faithfully the SaaS mirror matches it (target integrity >= 99%)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors.accounting import AccountingPort
from app.domain.models import Activity, Order, Transaction
from app.events.activity import emit


class AccountingOrchestrator:
    def __init__(self, port: AccountingPort) -> None:
        self.port = port

    def sync_pending(self, session: Session) -> dict:
        """Post orders that have no mirrored transaction yet. Idempotent:
        re-running never double-posts (keyed on order_id)."""
        currency = get_settings().currency
        placed = session.scalars(
            select(Activity).where(Activity.type == "order.placed", Activity.subject_type == "order")
        ).all()
        already = {t.order_id for t in session.scalars(select(Transaction)).all()}

        synced = 0
        for act in placed:
            order_id = act.subject_id
            if order_id in already:
                continue
            order = session.get(Order, order_id)
            if order and order.status == "cancelled":
                continue  # cancelled before sync — no sale voucher
            amount = order.total_amount if order else float(act.payload.get("total", 0.0))
            ext = self.port.post_transaction(
                order_id=order_id, amount=amount, currency=currency, kind="sale",
                memo=f"order {order_id}",
            )
            session.add(Transaction(
                order_id=order_id, external_id=ext.external_id, kind=ext.kind, amount=ext.amount,
                currency=ext.currency, status=ext.status, source="accounting_saas", occurred_at=ext.occurred_at,
            ))
            session.flush()
            emit(session, type="transaction.posted", subject_type="order", subject_id=order_id,
                 payload={"external_id": ext.external_id, "amount": ext.amount}, source="accounting_saas")
            if order:
                emit(session, type="transaction.posted", subject_type="customer", subject_id=order.customer_id,
                     payload={"order_id": order_id, "amount": ext.amount}, source="accounting_saas")
            already.add(order_id)
            synced += 1

        session.commit()
        return {"synced": synced}

    def post_refund(self, session: Session, order_id: str, amount: float | None = None) -> dict:
        """Issue a refund voucher for a (usually cancelled) order and mirror it."""
        currency = get_settings().currency
        order = session.get(Order, order_id)
        refund_amount = amount if amount is not None else (order.total_amount if order else 0.0)
        ext = self.port.post_transaction(
            order_id=order_id, amount=refund_amount, currency=currency, kind="refund",
            memo=f"refund {order_id}",
        )
        session.add(Transaction(
            order_id=order_id, external_id=ext.external_id, kind="refund", amount=ext.amount,
            currency=ext.currency, status=ext.status, source="accounting_saas", occurred_at=ext.occurred_at,
        ))
        session.flush()
        emit(session, type="transaction.refunded", subject_type="order", subject_id=order_id,
             payload={"external_id": ext.external_id, "amount": ext.amount}, source="accounting_saas")
        if order:
            emit(session, type="transaction.refunded", subject_type="customer", subject_id=order.customer_id,
                 payload={"order_id": order_id, "amount": ext.amount}, source="accounting_saas")
        session.commit()
        return {"order_id": order_id, "refunded": ext.amount, "external_id": ext.external_id}

    def reconcile(self, session: Session) -> dict:
        """Compare expected revenue (orders) against mirrored transactions."""
        order_ids = {
            a.subject_id for a in session.scalars(
                select(Activity).where(Activity.type == "order.placed", Activity.subject_type == "order")
            ).all()
        }
        txns = session.scalars(select(Transaction)).all()
        by_order: dict[str, list[Transaction]] = {}
        for t in txns:
            by_order.setdefault(t.order_id, []).append(t)

        matched, missing, mismatched = 0, [], []
        for order_id in order_ids:
            order = session.get(Order, order_id)
            # A cancelled order should net to zero (sale offset by refund).
            expected = 0.0 if (order and order.status == "cancelled") else (order.total_amount if order else 0.0)
            rows = by_order.get(order_id, [])
            if not rows:
                if expected == 0.0:  # cancelled with no vouchers is consistent
                    matched += 1
                else:
                    missing.append(order_id)
                continue
            actual = sum(r.amount if r.kind == "sale" else -r.amount for r in rows)
            if abs(actual - expected) < 0.01:
                matched += 1
            else:
                mismatched.append({"order_id": order_id, "expected": expected, "actual": round(actual, 2)})

        orphan = [t.external_id for t in txns if t.order_id not in order_ids]
        total = len(order_ids)
        integrity = round(matched / total, 4) if total else 1.0
        return {
            "total_orders": total,
            "matched": matched,
            "missing": missing,
            "mismatched": mismatched,
            "orphan_transactions": orphan,
            "integrity_rate": integrity,
            "healthy": integrity >= 0.99 and not orphan,
        }
