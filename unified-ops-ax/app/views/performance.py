"""Derived view — v_employee_performance. Computed from the Activity stream
(actor attribution) plus AS ticket load. No stored table."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import Activity, ASTicket, Employee


def employee_performance(session: Session, employee_id: str | None = None) -> list[dict]:
    query = select(Employee)
    if employee_id:
        query = query.where(Employee.id == employee_id)

    rows = []
    for emp in session.scalars(query).all():
        activities = session.scalars(
            select(Activity).where(Activity.actor_employee_id == emp.id)
        ).all()
        by_type: dict[str, int] = {}
        for act in activities:
            by_type[act.type] = by_type.get(act.type, 0) + 1

        as_resolved = session.scalar(
            select(func.count()).select_from(ASTicket).where(
                ASTicket.assignee_id == emp.id, ASTicket.status == "resolved"
            )
        ) or 0
        as_open = session.scalar(
            select(func.count()).select_from(ASTicket).where(
                ASTicket.assignee_id == emp.id, ASTicket.status != "resolved"
            )
        ) or 0

        rows.append({
            "employee_id": emp.id,
            "name": emp.name,
            "role": emp.role,
            "activity_count": len(activities),
            "by_type": by_type,
            "as_resolved": int(as_resolved),
            "as_open": int(as_open),
        })
    return rows
