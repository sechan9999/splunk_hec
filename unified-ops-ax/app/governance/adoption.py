"""Adoption metrics — the KPIs from the plan, computed from the event stream.
Measures whether the system is actually used and trusted (DAU, HITL approval,
knowledge coverage, accounting integrity)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors.accounting import build_accounting_adapter
from app.domain.models import Activity, ASTicket, Employee, FollowUp, KnowledgeItem
from app.orchestration.accounting import AccountingOrchestrator


def _ratio(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def adoption_metrics(session: Session, window_days: int = 7) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    total_emp = session.scalar(select(func.count()).select_from(Employee)) or 0
    active = session.scalar(
        select(func.count(func.distinct(Activity.actor_employee_id)))
        .where(Activity.occurred_at >= cutoff, Activity.actor_employee_id.isnot(None))
    ) or 0

    total_activity = session.scalar(select(func.count()).select_from(Activity)) or 0
    by_source = {
        src: cnt for src, cnt in session.execute(
            select(Activity.source, func.count()).group_by(Activity.source)
        ).all()
    }

    followups_total = session.scalar(select(func.count()).select_from(FollowUp)) or 0
    followups_sent = session.scalar(
        select(func.count()).select_from(FollowUp).where(FollowUp.status == "sent")
    ) or 0

    resolved = session.scalar(
        select(func.count()).select_from(ASTicket).where(ASTicket.status == "resolved")
    ) or 0
    knowledge = session.scalar(select(func.count()).select_from(KnowledgeItem)) or 0

    integrity = AccountingOrchestrator(build_accounting_adapter()).reconcile(session)["integrity_rate"]

    return {
        "window_days": window_days,
        "employees": {"total": total_emp, "active": active, "dau_ratio": _ratio(active, total_emp)},
        "activity": {"total": total_activity, "by_source": by_source},
        "hitl": {
            "followups_drafted": followups_total,
            "followups_sent": followups_sent,
            "approval_rate": _ratio(followups_sent, followups_total),
        },
        "knowledge_coverage": {
            "resolved_tickets": resolved,
            "knowledge_items": knowledge,
            "coverage": _ratio(knowledge, resolved),
        },
        "accounting_integrity": integrity,
    }
