from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.followup import FollowUpAgent
from app.agents.insights import InsightsAgent
from app.agents.knowledge import KnowledgeCaptureAgent
from app.agents.triage import ASTriageAgent
from app.db import get_session

router = APIRouter(prefix="/agents", tags=["ai-agents"])


@router.post("/insights")
def insights(session: Session = Depends(get_session)):
    return InsightsAgent(session).run()


@router.post("/triage/{ticket_id}")
def triage(ticket_id: str, session: Session = Depends(get_session)):
    try:
        return ASTriageAgent(session).run(ticket_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/knowledge/{ticket_id}")
def capture_knowledge(ticket_id: str, session: Session = Depends(get_session)):
    try:
        return KnowledgeCaptureAgent(session).run(ticket_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/followup/order/{order_id}")
def draft_followup(order_id: str, session: Session = Depends(get_session)):
    try:
        return FollowUpAgent(session).draft_for_order(order_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/followup/{followup_id}/approve")
def approve_followup(followup_id: str, session: Session = Depends(get_session)):
    try:
        return FollowUpAgent(session).approve_and_send(followup_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/followup/pending")
def list_pending_followups(session: Session = Depends(get_session)):
    """List all drafted customer follow-up messages waiting for human sign-off."""
    return {"pending": FollowUpAgent.list_pending(session)}

