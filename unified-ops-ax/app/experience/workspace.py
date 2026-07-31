"""Experience layer (L5) — role-based workspace assembly. Same SSOT, different
window: each widget binds to a derived view, gated by the caller's role, and
ordered by the role preset or the employee's saved layout (personalization)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.insights import InsightsAgent
from app.connectors.accounting import build_accounting_adapter
from app.domain.models import FollowUp, KnowledgeItem, ProductionJob, UserPreference
from app.orchestration.accounting import AccountingOrchestrator
from app.security.auth import Identity
from app.security.rls import scope_customers, scope_open_tickets
from app.views.inventory import inventory_status
from app.views.performance import employee_performance
from app.views.pipeline import pipeline

_ALL_ROLES = {"sales", "production", "as", "accounting", "manager"}


@dataclass
class Widget:
    id: str
    label: str
    roles: set[str]  # which roles may see it (manager implied via preset)
    render: Callable[[Session, Identity], object]


def _as_queue(session: Session, identity: Identity):
    rows = scope_open_tickets(session, identity)  # RLS: AS sees own/unassigned
    return [{"id": t.id, "summary": t.summary, "severity": t.severity, "status": t.status} for t in rows]


def _followup_queue(session: Session, identity: Identity):
    rows = session.scalars(select(FollowUp).where(FollowUp.status == "draft")).all()
    return [{"id": f.id, "customer_id": f.customer_id, "channel": f.channel} for f in rows]


def _production_queue(session: Session, identity: Identity):
    rows = session.scalars(select(ProductionJob).where(ProductionJob.status != "done")).all()
    return [{"id": j.id, "order_id": j.order_id, "status": j.status} for j in rows]


def _customer_directory(session: Session, identity: Identity):
    rows = scope_customers(session, identity)  # RLS: sales sees own accounts
    return [{"id": c.id, "name": c.name, "segment": c.segment} for c in rows]


def _knowledge_recent(session: Session, identity: Identity):
    rows = session.scalars(select(KnowledgeItem).order_by(KnowledgeItem.created_at.desc()).limit(10)).all()
    return [{"id": k.id, "title": k.title, "tags": k.tags, "status": k.status} for k in rows]


def _accounting_health(session: Session, identity: Identity):
    return AccountingOrchestrator(build_accounting_adapter()).reconcile(session)


def _insights(session: Session, identity: Identity):
    return InsightsAgent(session).preview()  # read-only, no side effects


WIDGETS: dict[str, Widget] = {
    "pipeline": Widget("pipeline", "영업 파이프라인", {"sales", "manager"}, lambda s, i: pipeline(s)),
    "inventory": Widget("inventory", "재고 현황", {"production", "accounting", "manager"}, lambda s, i: inventory_status(s)),
    "performance": Widget("performance", "성과 대시보드", {"manager"}, lambda s, i: employee_performance(s)),
    "accounting_health": Widget("accounting_health", "회계 정합", {"accounting", "manager"}, _accounting_health),
    "insights": Widget("insights", "운영 인사이트", {"manager"}, _insights),
    "as_queue": Widget("as_queue", "AS 대기열", {"as", "manager"}, _as_queue),
    "followup_queue": Widget("followup_queue", "팔로업 초안", {"sales", "as", "manager"}, _followup_queue),
    "production_queue": Widget("production_queue", "공정 작업 큐", {"production", "manager"}, _production_queue),
    "customer_directory": Widget("customer_directory", "고객 목록", {"sales", "as", "manager"}, _customer_directory),
    "knowledge_recent": Widget("knowledge_recent", "최근 지식", _ALL_ROLES, _knowledge_recent),
}

# Default widget set per role (personalization overrides this).
ROLE_PRESETS: dict[str, list[str]] = {
    "sales": ["pipeline", "customer_directory", "followup_queue"],
    "production": ["production_queue", "inventory"],
    "as": ["as_queue", "followup_queue", "knowledge_recent"],
    "accounting": ["accounting_health", "inventory"],
    "manager": ["pipeline", "performance", "inventory", "accounting_health", "insights"],
}


def _visible(widget_id: str, role: str) -> bool:
    widget = WIDGETS.get(widget_id)
    return bool(widget) and (role == "manager" or role in widget.roles)


def get_layout(session: Session, identity: Identity) -> list[str]:
    pref = session.scalar(select(UserPreference).where(UserPreference.employee_id == identity.employee_id))
    if pref and pref.layout:
        return [w for w in pref.layout if _visible(w, identity.role)]  # RBAC defense on saved layout
    return ROLE_PRESETS.get(identity.role, [])


def save_layout(session: Session, identity: Identity, layout: list[str]) -> list[str]:
    cleaned = [w for w in layout if w in WIDGETS]
    pref = session.scalar(select(UserPreference).where(UserPreference.employee_id == identity.employee_id))
    if pref is None:
        pref = UserPreference(employee_id=identity.employee_id, layout=cleaned)
        session.add(pref)
    else:
        pref.layout = cleaned
    session.commit()
    return cleaned


def assemble_workspace(session: Session, identity: Identity) -> dict:
    widgets = []
    for widget_id in get_layout(session, identity):
        if not _visible(widget_id, identity.role):
            continue
        widget = WIDGETS[widget_id]
        widgets.append({"id": widget.id, "label": widget.label, "data": widget.render(session, identity)})
    return {
        "employee": {"id": identity.employee_id, "name": identity.name, "role": identity.role},
        "widgets": widgets,
    }
