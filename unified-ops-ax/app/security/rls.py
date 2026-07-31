"""Row-Level Security (application layer). Non-manager callers see only rows
they are entitled to: sales -> own accounts, AS -> assigned/unassigned tickets,
accounting -> all (financial oversight). Managers see everything. (Production
can additionally enforce Postgres RLS policies on the same predicates.)"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.models import ASTicket, Customer
from app.security.auth import Identity

FULL_CUSTOMER_ROLES = {"manager", "accounting"}


def can_view_customer(session: Session, identity: Identity, customer_id: str) -> bool:
    if identity.role in FULL_CUSTOMER_ROLES:
        return True
    customer = session.get(Customer, customer_id)
    if customer is None:
        return False
    if identity.role == "sales":
        return customer.owner_employee_id == identity.employee_id
    if identity.role == "as":
        return session.scalar(
            select(ASTicket.id).where(
                ASTicket.customer_id == customer_id, ASTicket.assignee_id == identity.employee_id
            ).limit(1)
        ) is not None
    return False


def scope_customers(session: Session, identity: Identity, limit: int = 50):
    stmt = select(Customer)
    if identity.role in FULL_CUSTOMER_ROLES:
        pass
    elif identity.role == "sales":
        stmt = stmt.where(Customer.owner_employee_id == identity.employee_id)
    elif identity.role == "as":
        assigned = select(ASTicket.customer_id).where(ASTicket.assignee_id == identity.employee_id)
        stmt = stmt.where(Customer.id.in_(assigned))
    else:
        stmt = stmt.where(Customer.id.is_(None))  # deny by default
    return session.scalars(stmt.limit(limit)).all()


def scope_open_tickets(session: Session, identity: Identity):
    stmt = select(ASTicket).where(ASTicket.status != "resolved")
    if identity.role == "manager":
        pass
    elif identity.role == "as":
        stmt = stmt.where(or_(ASTicket.assignee_id == identity.employee_id, ASTicket.assignee_id.is_(None)))
    elif identity.role in FULL_CUSTOMER_ROLES:  # accounting sees all (oversight)
        pass
    else:
        stmt = stmt.where(ASTicket.id.is_(None))
    return session.scalars(stmt).all()
