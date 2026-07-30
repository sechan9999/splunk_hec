"""Derived view — v_inventory_status. Real-time availability from stock minus
quantity allocated to orders still in the pipeline (placed/in_production)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import Order, OrderLine, Product

_OPEN_ORDER_STATES = ("placed", "in_production")


def inventory_status(session: Session) -> list[dict]:
    rows = []
    for product in session.scalars(select(Product)).all():
        allocated = session.scalar(
            select(func.coalesce(func.sum(OrderLine.qty), 0))
            .select_from(OrderLine)
            .join(Order, OrderLine.order_id == Order.id)
            .where(OrderLine.product_id == product.id, Order.status.in_(_OPEN_ORDER_STATES))
        ) or 0
        allocated = int(allocated)
        rows.append({
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "stock_qty": product.stock_qty,
            "allocated": allocated,
            "available": product.stock_qty - allocated,
            "bom": product.bom,
        })
    return rows
