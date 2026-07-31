"""Domain services — write paths that keep the event stream authoritative.
Placing an order emits `order.placed`, auto-creates a ProductionJob, and
emits `production.queued`; a customer-anchored activity feeds the 360 view.
This is the 'handoff automation' that replaces manual inter-dept handover."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.models import ASTicket, Order, OrderLine, Product, ProductionJob
from app.events.activity import emit


def place_order(
    session: Session,
    *,
    customer_id: str,
    lines: list[dict],
    actor_employee_id: str | None = None,
) -> Order:
    order = Order(customer_id=customer_id, status="placed")
    session.add(order)
    session.flush()

    total = 0.0
    for line in lines:
        product = session.get(Product, line["product_id"])
        price = line.get("unit_price", product.unit_price if product else 0.0)
        qty = line.get("qty", 1)
        session.add(OrderLine(order_id=order.id, product_id=line["product_id"], qty=qty, unit_price=price))
        total += price * qty
    order.total_amount = round(total, 2)

    job = ProductionJob(order_id=order.id, status="queued", steps=[])
    session.add(job)
    session.flush()

    emit(session, type="order.placed", subject_type="order", subject_id=order.id,
         actor_employee_id=actor_employee_id, payload={"total": order.total_amount})
    emit(session, type="order.placed", subject_type="customer", subject_id=customer_id,
         actor_employee_id=actor_employee_id, payload={"order_id": order.id, "total": order.total_amount})
    emit(session, type="production.queued", subject_type="production", subject_id=job.id,
         payload={"order_id": order.id})

    session.commit()
    return order


def mark_delivered(session: Session, order_id: str) -> Order:
    order = session.get(Order, order_id)
    order.status = "delivered"
    emit(session, type="delivery.done", subject_type="order", subject_id=order.id,
         payload={"customer_id": order.customer_id})
    emit(session, type="delivery.done", subject_type="customer", subject_id=order.customer_id,
         payload={"order_id": order.id})
    session.commit()
    return order


def cancel_order(session: Session, order_id: str) -> Order:
    order = session.get(Order, order_id)
    order.status = "cancelled"
    emit(session, type="order.cancelled", subject_type="order", subject_id=order.id,
         payload={"customer_id": order.customer_id, "amount": order.total_amount})
    emit(session, type="order.cancelled", subject_type="customer", subject_id=order.customer_id,
         payload={"order_id": order.id})
    session.commit()
    return order


def open_as_ticket(session: Session, *, customer_id: str, summary: str, order_id: str | None = None) -> ASTicket:
    ticket = ASTicket(customer_id=customer_id, order_id=order_id, summary=summary, status="open")
    session.add(ticket)
    session.flush()
    emit(session, type="as.opened", subject_type="as", subject_id=ticket.id,
         payload={"customer_id": customer_id, "summary": summary})
    emit(session, type="as.opened", subject_type="customer", subject_id=customer_id,
         payload={"ticket_id": ticket.id})
    session.commit()
    return ticket


def resolve_as_ticket(session: Session, ticket_id: str, resolution: str) -> ASTicket:
    ticket = session.get(ASTicket, ticket_id)
    ticket.status = "resolved"
    ticket.resolution = resolution
    emit(session, type="as.resolved", subject_type="as", subject_id=ticket.id,
         actor_employee_id=ticket.assignee_id, payload={"resolution": resolution})
    emit(session, type="as.resolved", subject_type="customer", subject_id=ticket.customer_id,
         payload={"ticket_id": ticket.id})
    session.commit()
    return ticket
