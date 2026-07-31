"""MCP tool registry — the hub capabilities exposed to external AI. Read-only
plus safe, reversible internal actions (triage). External/irreversible actions
(follow-up send, refund) are intentionally NOT exposed — those stay behind the
human-approval gate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.triage import ASTriageAgent
from app.connectors.accounting import build_accounting_adapter
from app.domain.models import ASTicket
from app.orchestration.accounting import AccountingOrchestrator
from app.rag.service import answer
from app.views.customer360 import customer_360
from app.views.inventory import inventory_status
from app.views.pipeline import pipeline


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[Session, dict], object]

    def public(self) -> dict:
        return {"name": self.name, "description": self.description, "inputSchema": self.input_schema}


def _search_knowledge(session, args):
    return answer(args["query"], role=args.get("role", "manager"), k=args.get("k", 5))


def _get_customer_360(session, args):
    view = customer_360(session, args["customer_id"])
    return view if view is not None else {"error": "customer not found"}


def _list_open_tickets(session, args):
    rows = session.scalars(select(ASTicket).where(ASTicket.status != "resolved")).all()
    return [{"id": t.id, "summary": t.summary, "category": t.category, "severity": t.severity,
             "status": t.status, "assignee_id": t.assignee_id} for t in rows]


def _get_pipeline(session, args):
    return pipeline(session)


def _get_inventory(session, args):
    return inventory_status(session)


def _reconcile_accounting(session, args):
    return AccountingOrchestrator(build_accounting_adapter()).reconcile(session)


def _triage_ticket(session, args):
    return ASTriageAgent(session).run(args["ticket_id"])


_STR = {"type": "string"}
TOOLS: list[Tool] = [
    Tool("search_knowledge", "사내 문서·지식을 RAG로 검색(권한 트리밍). role로 접근범위 지정.",
         {"type": "object", "properties": {"query": _STR, "role": _STR, "k": {"type": "integer"}},
          "required": ["query"]}, _search_knowledge),
    Tool("get_customer_360", "고객의 전체 여정(리드·주문·공정·AS·팔로업 타임라인) 조회.",
         {"type": "object", "properties": {"customer_id": _STR}, "required": ["customer_id"]}, _get_customer_360),
    Tool("list_open_tickets", "미해결 AS 티켓 목록.",
         {"type": "object", "properties": {}}, _list_open_tickets),
    Tool("get_pipeline", "마케팅 리드→매출 파이프라인 지표.",
         {"type": "object", "properties": {}}, _get_pipeline),
    Tool("get_inventory", "실시간 재고 현황(할당·가용).",
         {"type": "object", "properties": {}}, _get_inventory),
    Tool("reconcile_accounting", "주문 대비 회계 미러 정합 대조(integrity_rate·missing·mismatch).",
         {"type": "object", "properties": {}}, _reconcile_accounting),
    Tool("triage_ticket", "AS 티켓을 분류·심각도·담당 배정(안전한 내부 액션, override 가능).",
         {"type": "object", "properties": {"ticket_id": _STR}, "required": ["ticket_id"]}, _triage_ticket),
]

TOOLS_BY_NAME = {t.name: t for t in TOOLS}
