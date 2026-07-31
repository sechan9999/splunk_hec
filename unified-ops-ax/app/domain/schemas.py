from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CustomerIn(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    segment: str | None = None
    owner_employee_id: str | None = None


class ProductIn(BaseModel):
    sku: str
    name: str
    unit_price: float = 0.0
    stock_qty: int = 0


class OrderLineIn(BaseModel):
    product_id: str
    qty: int = 1
    unit_price: float | None = None


class OrderIn(BaseModel):
    customer_id: str
    lines: list[OrderLineIn]
    actor_employee_id: str | None = None


class IngestIn(BaseModel):
    title: str
    content: str
    acl: list[str] = []
    source: str = "local"


class IngestFolderIn(BaseModel):
    path: str


class RagQueryIn(BaseModel):
    query: str
    role: str = "sales"
    employee_id: str | None = None
    k: int = 5


class ChatIn(BaseModel):
    message: str
    provider: str | None = None
    model: str | None = None


class ScheduleEventIn(BaseModel):
    title: str
    start: datetime
    end: datetime | None = None
    employee_id: str | None = None
    customer_id: str | None = None


class EmployeeIn(BaseModel):
    name: str
    role: str  # sales | production | as | accounting | manager
    principals: list[str] = []


class ASTicketIn(BaseModel):
    customer_id: str
    summary: str
    order_id: str | None = None


class ResolveIn(BaseModel):
    resolution: str
