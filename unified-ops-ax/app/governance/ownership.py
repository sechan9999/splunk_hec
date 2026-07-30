"""Data ownership registry — accountability for each domain (design §7)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import DataOwner

DOMAINS = ["marketing", "crm", "production", "inventory", "as", "accounting", "schedule", "knowledge", "performance"]


def list_owners(session: Session) -> list[dict]:
    rows = session.scalars(select(DataOwner)).all()
    return [
        {"domain": o.domain, "owner_employee_id": o.owner_employee_id,
         "classification": o.classification, "notes": o.notes}
        for o in rows
    ]


def set_owner(session: Session, *, domain: str, owner_employee_id: str | None,
              classification: str = "internal", notes: str | None = None) -> DataOwner:
    owner = session.scalar(select(DataOwner).where(DataOwner.domain == domain))
    if owner is None:
        owner = DataOwner(domain=domain)
        session.add(owner)
    owner.owner_employee_id = owner_employee_id
    owner.classification = classification
    owner.notes = notes
    session.commit()
    return owner


def coverage(session: Session) -> dict:
    assigned = {o["domain"] for o in list_owners(session) if o["owner_employee_id"]}
    return {"domains": DOMAINS, "assigned": sorted(assigned),
            "unassigned": sorted(set(DOMAINS) - assigned)}
