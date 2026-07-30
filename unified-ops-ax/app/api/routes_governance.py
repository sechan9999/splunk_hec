from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.governance.adoption import adoption_metrics
from app.governance.audit import audit_trail
from app.governance.dashboard import governance_dashboard
from app.governance.ownership import list_owners, set_owner
from app.security.auth import Identity, require_manager

router = APIRouter(prefix="/governance", tags=["governance"])


class OwnerIn(BaseModel):
    domain: str
    owner_employee_id: str | None = None
    classification: str = "internal"
    notes: str | None = None


@router.get("/dashboard")
def dashboard(_: Identity = Depends(require_manager), session: Session = Depends(get_session)):
    return governance_dashboard(session)


@router.get("/adoption")
def adoption(window_days: int = 7, _: Identity = Depends(require_manager), session: Session = Depends(get_session)):
    return adoption_metrics(session, window_days)


@router.get("/audit")
def audit(
    type: str | None = None,
    source: str | None = None,
    subject_type: str | None = None,
    since_days: int | None = None,
    limit: int = 100,
    _: Identity = Depends(require_manager),
    session: Session = Depends(get_session),
):
    return audit_trail(session, type=type, source=source, subject_type=subject_type,
                       since_days=since_days, limit=limit)


@router.get("/ownership")
def ownership(_: Identity = Depends(require_manager), session: Session = Depends(get_session)):
    return list_owners(session)


@router.post("/ownership")
def upsert_ownership(body: OwnerIn, _: Identity = Depends(require_manager), session: Session = Depends(get_session)):
    owner = set_owner(session, domain=body.domain, owner_employee_id=body.owner_employee_id,
                      classification=body.classification, notes=body.notes)
    return {"domain": owner.domain, "owner_employee_id": owner.owner_employee_id,
            "classification": owner.classification}
