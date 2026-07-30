"""Canonical data model (SSOT). Activity is the atomic event store that
feeds performance, accounting reconciliation, handoff automation, and the
customer-360 view as derived views."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# --- Anchor entities ---------------------------------------------------------
class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    segment: Mapped[str | None] = mapped_column(String(50), nullable=True)

    orders: Mapped[list[Order]] = relationship(back_populates="customer")
    leads: Mapped[list[Lead]] = relationship(back_populates="customer")


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50))  # sales | production | as | accounting | manager
    # Principals grant document access (security trimming). e.g. ["grp:sales","usr:<id>"]
    principals: Mapped[list] = mapped_column(JSON, default=list)
    # Bearer token for API auth (issued on demand). Identity derives from this.
    api_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    sku: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    bom: Mapped[list] = mapped_column(JSON, default=list)  # [{component_sku, qty}]


# --- Flow entities -----------------------------------------------------------
class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    source: Mapped[str] = mapped_column(String(50), default="unknown")  # ad | referral | inbound
    status: Mapped[str] = mapped_column(String(30), default="new")  # new | qualified | converted | lost
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="leads")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[str] = mapped_column(String(30), default="placed")  # placed | in_production | delivered | closed
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    lines: Mapped[list[OrderLine]] = relationship(back_populates="order", cascade="all, delete-orphan")
    production_job: Mapped[ProductionJob | None] = relationship(back_populates="order", uselist=False)


class OrderLine(Base):
    __tablename__ = "order_lines"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)

    order: Mapped[Order] = relationship(back_populates="lines")


class ProductionJob(Base, TimestampMixin):
    __tablename__ = "production_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued")  # queued | running | done
    steps: Mapped[list] = mapped_column(JSON, default=list)  # [{name, status, at}]

    order: Mapped[Order] = relationship(back_populates="production_job")


class ASTicket(Base, TimestampMixin):
    __tablename__ = "as_tickets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")  # open | assigned | resolved
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class FollowUp(Base, TimestampMixin):
    __tablename__ = "followups"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    channel: Mapped[str] = mapped_column(String(30), default="email")
    status: Mapped[str] = mapped_column(String(30), default="draft")  # draft | approved | sent
    draft: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class KnowledgeItem(Base, TimestampMixin):
    __tablename__ = "knowledge_items"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(String(4000))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    source_activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | reviewed


# --- Event store (the heart) -------------------------------------------------
class Activity(Base):
    """Every departmental action becomes one Activity row. Anchored to a
    subject (customer/order/...) and an actor (employee). All cross-domain
    connectivity derives from this stream."""
    __tablename__ = "activities"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    type: Mapped[str] = mapped_column(String(60), index=True)  # lead.created | order.placed | as.resolved ...
    actor_employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    subject_type: Mapped[str] = mapped_column(String(30), index=True)  # customer | order | production | as
    subject_id: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(20), default="app")  # app | accounting_saas | calendar | agent
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    # Outbox flag — the event dispatcher marks activities it has processed.
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


# --- Accounting / Calendar (SaaS orchestration, P2) -------------------------
class Transaction(Base, TimestampMixin):
    """Local mirror of an accounting-SaaS voucher. The Activity stream stays
    the source of truth; this row is the reconciled shadow of the external
    system (adapter pattern keeps the SaaS out of the core)."""
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="sale")  # sale | refund
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="KRW")
    status: Mapped[str] = mapped_column(String(20), default="posted")  # pending | posted | failed
    source: Mapped[str] = mapped_column(String(30), default="accounting_saas")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ScheduleEvent(Base, TimestampMixin):
    """Calendar entry, two-way synced with a calendar SaaS via external_id."""
    __tablename__ = "schedule_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    title: Mapped[str] = mapped_column(String(300))
    employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="local")  # local | msgraph | google
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | synced
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- RAG / Enterprise AI Platform -------------------------------------------
class Document(Base, TimestampMixin):
    """Ingested internal document. `acl` is the security-trimming principal
    list mirrored from the source system (SharePoint/Teams)."""
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    source: Mapped[str] = mapped_column(String(40), default="local")  # sharepoint | teams | local
    external_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    title: Mapped[str] = mapped_column(String(400))
    uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    acl: Mapped[list] = mapped_column(JSON, default=list)  # principals allowed to read
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DataOwner(Base, TimestampMixin):
    """Governance registry — who owns each data domain and its classification.
    Accountability layer over the SSOT (design §7 data ownership)."""
    __tablename__ = "data_owners"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    domain: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # crm | production | accounting ...
    owner_employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    classification: Mapped[str] = mapped_column(String(20), default="internal")  # public | internal | confidential
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class UserPreference(Base, TimestampMixin):
    """Per-employee workspace layout — the personalization behind role-based
    custom UX (L5). `layout` is an ordered list of widget ids."""
    __tablename__ = "user_preferences"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), unique=True, index=True)
    layout: Mapped[list] = mapped_column(JSON, default=list)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(String(8000))
    # acl snapshotted onto the chunk so the vector store can trim without a join
    acl: Mapped[list] = mapped_column(JSON, default=list)

    document: Mapped[Document] = relationship(back_populates="chunks")
