"""Derived view — v_pipeline. Marketing lead -> revenue funnel."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Lead, Order


def pipeline(session: Session) -> dict:
    leads = session.scalars(select(Lead)).all()
    by_status: dict[str, int] = {}
    for lead in leads:
        by_status[lead.status] = by_status.get(lead.status, 0) + 1

    total = len(leads)
    converted = by_status.get("converted", 0)
    orders = session.scalars(select(Order)).all()
    revenue = round(sum(o.total_amount for o in orders), 2)

    return {
        "lead_total": total,
        "by_status": by_status,
        "converted": converted,
        "conversion_rate": round(converted / total, 4) if total else 0.0,
        "orders": len(orders),
        "revenue": revenue,
    }
