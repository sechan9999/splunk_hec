"""Knowledge Capture agent. Turns a resolved AS ticket into a structured,
reviewable KnowledgeItem (draft) and indexes it into the RAG store so future
tickets surface it — the tacit->explicit loop. No external action, so the
draft is auto-created into a review queue (status=draft)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.rules import classify
from app.ai.gateway import AIGateway, get_gateway
from app.domain.models import ASTicket, KnowledgeItem
from app.events.activity import emit
from app.rag.ingest import ingest_document

# Knowledge is shared org-wide by default so retrieval helps everyone.
_KNOWLEDGE_ACL = ["grp:all"]


class KnowledgeCaptureAgent:
    def __init__(self, session: Session, gateway: AIGateway | None = None) -> None:
        self.session = session
        self.gateway = gateway or get_gateway()

    def run(self, ticket_id: str) -> dict:
        ticket = self.session.get(ASTicket, ticket_id)
        if ticket is None:
            raise ValueError(f"ticket not found: {ticket_id}")

        category = ticket.category or classify(ticket.summary or "")[0]
        title = f"[{category}] {(ticket.summary or 'AS resolution')[:80]}"
        body = self._structure(ticket, category)
        tags = [category, "as"]

        item = KnowledgeItem(title=title, body=body, tags=tags, status="draft")
        self.session.add(item)
        self.session.flush()

        # Close the loop: index the knowledge so the triage/RAG side can find it.
        ingest_document(
            self.session, title=title, content=body, acl=_KNOWLEDGE_ACL,
            source="knowledge", external_id=item.id, meta={"knowledge_id": item.id, "category": category},
        )
        emit(self.session, type="knowledge.captured", subject_type="as", subject_id=ticket.id,
             payload={"knowledge_id": item.id, "category": category}, source="agent")
        self.session.commit()

        return {"knowledge_id": item.id, "title": title, "tags": tags, "status": item.status}

    def _structure(self, ticket: ASTicket, category: str) -> str:
        template = (
            f"증상(Symptom): {ticket.summary or '-'}\n"
            f"카테고리(Category): {category} / 심각도(Severity): {ticket.severity or '-'}\n"
            f"조치(Resolution): {ticket.resolution or '-'}\n"
            f"재발방지(Prevention): (리뷰 필요)"
        )
        try:
            result = self.gateway.chat([
                {"role": "system", "content": "You structure resolved support tickets into a knowledge base "
                                              "entry with Symptom / Cause / Resolution / Prevention. Be concise."},
                {"role": "user", "content": f"Ticket summary: {ticket.summary}\nResolution: {ticket.resolution}"},
            ])
            narrative = result.get("content", "").strip()
            # Keep the deterministic template as the backbone; append LLM narrative when present.
            return f"{template}\n\n---\n{narrative}" if narrative else template
        except Exception:
            return template
