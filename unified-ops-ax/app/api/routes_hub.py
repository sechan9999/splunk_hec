from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.models import Customer, Employee, Product
from app.domain.schemas import ASTicketIn, CustomerIn, EmployeeIn, OrderIn, ProductIn, ResolveIn
from app.domain.services import cancel_order, mark_delivered, open_as_ticket, place_order, resolve_as_ticket
from app.security.auth import Identity, current_identity
from app.security.pii import get_cipher
from app.security.rls import can_view_customer, scope_customers
from app.views.customer360 import customer_360

router = APIRouter(prefix="/hub", tags=["hub"])


@router.post("/customers")
def create_customer(body: CustomerIn, session: Session = Depends(get_session)):
    cipher = get_cipher()
    data = body.model_dump()
    data["email"] = cipher.encrypt(data.get("email"))  # PII encrypted at rest
    data["phone"] = cipher.encrypt(data.get("phone"))
    customer = Customer(**data)
    session.add(customer)
    session.commit()
    return {"id": customer.id, "name": customer.name}


@router.get("/me/customers")
def my_customers(identity: Identity = Depends(current_identity), session: Session = Depends(get_session)):
    rows = scope_customers(session, identity)  # RLS-scoped
    return [{"id": c.id, "name": c.name, "segment": c.segment} for c in rows]


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str, identity: Identity = Depends(current_identity),
                 session: Session = Depends(get_session)):
    if not can_view_customer(session, identity, customer_id):
        raise HTTPException(403, "not entitled to this customer")
    c = session.get(Customer, customer_id)
    if c is None:
        raise HTTPException(404, "customer not found")
    cipher = get_cipher()
    return {"id": c.id, "name": c.name, "segment": c.segment,
            "email": cipher.decrypt(c.email), "phone": cipher.decrypt(c.phone)}  # PII decrypted for entitled caller


@router.get("/customers/{customer_id}/360")
def get_customer_360(customer_id: str, identity: Identity = Depends(current_identity),
                     session: Session = Depends(get_session)):
    if not can_view_customer(session, identity, customer_id):
        raise HTTPException(403, "not entitled to this customer")
    view = customer_360(session, customer_id)
    if view is None:
        raise HTTPException(404, "customer not found")
    return view


@router.post("/products")
def create_product(body: ProductIn, session: Session = Depends(get_session)):
    product = Product(**body.model_dump())
    session.add(product)
    session.commit()
    return {"id": product.id, "sku": product.sku}


@router.post("/orders")
def create_order(body: OrderIn, session: Session = Depends(get_session)):
    order = place_order(
        session,
        customer_id=body.customer_id,
        lines=[l.model_dump(exclude_none=True) for l in body.lines],
        actor_employee_id=body.actor_employee_id,
    )
    return {"id": order.id, "status": order.status, "total_amount": order.total_amount}


@router.post("/orders/{order_id}/deliver")
def deliver_order(order_id: str, session: Session = Depends(get_session)):
    order = mark_delivered(session, order_id)
    return {"id": order.id, "status": order.status}


@router.post("/orders/{order_id}/cancel")
def cancel_order_route(order_id: str, session: Session = Depends(get_session)):
    order = cancel_order(session, order_id)
    return {"id": order.id, "status": order.status}


@router.post("/employees")
def create_employee(body: EmployeeIn, session: Session = Depends(get_session)):
    employee = Employee(**body.model_dump())
    session.add(employee)
    session.commit()
    return {"id": employee.id, "name": employee.name, "role": employee.role}


@router.post("/employees/{employee_id}/token")
def issue_employee_token(employee_id: str, session: Session = Depends(get_session)):
    from app.security.auth import issue_token

    employee = session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(404, "employee not found")
    return {"employee_id": employee.id, "token": issue_token(session, employee)}


@router.post("/as-tickets")
def create_as_ticket(body: ASTicketIn, session: Session = Depends(get_session)):
    ticket = open_as_ticket(session, customer_id=body.customer_id, summary=body.summary, order_id=body.order_id)
    return {"id": ticket.id, "status": ticket.status}


@router.post("/as-tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, body: ResolveIn, session: Session = Depends(get_session)):
    ticket = resolve_as_ticket(session, ticket_id, body.resolution)
    return {"id": ticket.id, "status": ticket.status}
