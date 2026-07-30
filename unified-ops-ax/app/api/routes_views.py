from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.views.inventory import inventory_status
from app.views.performance import employee_performance
from app.views.pipeline import pipeline

router = APIRouter(prefix="/views", tags=["derived-views"])


@router.get("/performance")
def performance(employee_id: str | None = None, session: Session = Depends(get_session)):
    return employee_performance(session, employee_id)


@router.get("/inventory")
def inventory(session: Session = Depends(get_session)):
    return inventory_status(session)


@router.get("/pipeline")
def pipeline_view(session: Session = Depends(get_session)):
    return pipeline(session)
