"""Derived view — a customer's full journey assembled from the Activity
stream plus flow entities. No separate storage; computed on read."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Activity, ASTicket, Customer, FollowUp, Lead, Order


def customer_360(session: Session, customer_id: str) -> dict | None:
    customer = session.get(Customer, customer_id)
    if not customer:
        return None

    leads = session.scalars(select(Lead).where(Lead.customer_id == customer_id)).all()
    orders = session.scalars(select(Order).where(Order.customer_id == customer_id)).all()
    tickets = session.scalars(select(ASTicket).where(ASTicket.customer_id == customer_id)).all()
    followups = session.scalars(select(FollowUp).where(FollowUp.customer_id == customer_id)).all()
    timeline = session.scalars(
        select(Activity)
        .where(Activity.subject_type == "customer", Activity.subject_id == customer_id)
        .order_by(Activity.occurred_at.desc())
    ).all()

    return {
        "customer": {"id": customer.id, "name": customer.name, "segment": customer.segment},
        "kpi": {
            "orders": len(orders),
            "lifetime_value": round(sum(o.total_amount for o in orders), 2),
            "open_as_tickets": sum(1 for t in tickets if t.status != "resolved"),
        },
        "leads": [{"id": l.id, "status": l.status, "source": l.source} for l in leads],
        "orders": [{"id": o.id, "status": o.status, "amount": o.total_amount} for o in orders],
        "as_tickets": [{"id": t.id, "status": t.status, "severity": t.severity} for t in tickets],
        "followups": [{"id": f.id, "status": f.status, "channel": f.channel} for f in followups],
        "timeline": [
            {"type": a.type, "at": a.occurred_at.isoformat(), "source": a.source, "payload": a.payload}
            for a in timeline
        ],
    }
