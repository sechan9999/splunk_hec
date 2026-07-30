"""AS Triage agent. Classifies an incoming ticket (rules), recommends the
least-loaded owner in the responsible role, and applies it. Assignment is
internal and reversible (override allowed), so no human gate is required —
but the decision and rationale are recorded as a source=agent Activity."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.rules import CATEGORY_ROLE, classify
from app.ai.gateway import AIGateway, get_gateway
from app.domain.models import ASTicket, Employee
from app.events.activity import emit


class ASTriageAgent:
    def __init__(self, session: Session, gateway: AIGateway | None = None) -> None:
        self.session = session
        self.gateway = gateway or get_gateway()

    def run(self, ticket_id: str, *, apply: bool = True) -> dict:
        ticket = self.session.get(ASTicket, ticket_id)
        if ticket is None:
            raise ValueError(f"ticket not found: {ticket_id}")

        category, severity = classify(ticket.summary or "")
        assignee = self._pick_assignee(category)
        rationale = self._llm_rationale(ticket.summary or "", category, severity)

        if apply:
            ticket.category = category
            ticket.severity = severity
            ticket.assignee_id = assignee.id if assignee else None
            ticket.status = "assigned" if assignee else "open"
            emit(self.session, type="as.triaged", subject_type="as", subject_id=ticket.id,
                 actor_employee_id=assignee.id if assignee else None,
                 payload={"category": category, "severity": severity,
                          "assignee_id": assignee.id if assignee else None, "rationale": rationale},
                 source="agent")
            self.session.commit()

        return {
            "ticket_id": ticket.id,
            "category": category,
            "severity": severity,
            "assignee_id": assignee.id if assignee else None,
            "assignee_name": assignee.name if assignee else None,
            "rationale": rationale,
            "applied": apply,
        }

    def _pick_assignee(self, category: str) -> Employee | None:
        role = CATEGORY_ROLE.get(category, "as")
        candidates = self.session.scalars(select(Employee).where(Employee.role == role)).all()
        if not candidates:
            return None

        def open_load(emp: Employee) -> int:
            return self.session.scalar(
                select(func.count()).select_from(ASTicket).where(
                    ASTicket.assignee_id == emp.id, ASTicket.status != "resolved"
                )
            ) or 0

        return min(candidates, key=open_load)

    def _llm_rationale(self, summary: str, category: str, severity: str) -> str:
        try:
            result = self.gateway.chat([
                {"role": "system", "content": "You are an after-sales triage assistant. Reply with one concise sentence."},
                {"role": "user", "content": f"Ticket: {summary}\nRouted as category={category}, severity={severity}. Briefly justify the routing."},
            ])
            return result["content"]
        except Exception:
            return ""  # rationale is non-authoritative; routing already decided by rules
