"""Auth — resolve the caller's identity from a bearer token instead of a
request parameter (closes the 'role as request param' gap). role and
principals are derived server-side from the authenticated Employee."""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.models import Employee
from app.security.rbac import principals_for


@dataclass
class Identity:
    employee_id: str
    name: str
    role: str
    principals: set[str]


def issue_token(session: Session, employee: Employee) -> str:
    token = secrets.token_urlsafe(24)
    employee.api_token = token
    session.commit()
    return token


def resolve_identity(session: Session, token: str) -> Identity:
    employee = session.scalar(select(Employee).where(Employee.api_token == token))
    if employee is None:
        raise HTTPException(401, "invalid token")
    return Identity(employee.id, employee.name, employee.role, principals_for(employee.role, employee.id))


def current_identity(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Identity:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    return resolve_identity(session, authorization.split(" ", 1)[1])
