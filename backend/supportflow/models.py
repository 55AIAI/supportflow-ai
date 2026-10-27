import time
import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid.uuid4())


def now():
    return int(time.time())


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("org_id", "reference"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    reference: Mapped[str] = mapped_column(String(30))
    customer_key: Mapped[str] = mapped_column(String(80))
    product: Mapped[str] = mapped_column(String(150))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="KZT")
    status: Mapped[str] = mapped_column(String(20), default="delivered")
    delivered_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    return_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Knowledge(Base):
    __tablename__ = "knowledge"
    __table_args__ = (UniqueConstraint("org_id", "kind"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)
    return_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(Integer, default=now)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    subject: Mapped[str] = mapped_column(String(180))
    customer_name: Mapped[str] = mapped_column(String(80))
    customer_key: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    category: Mapped[str] = mapped_column(String(20), default="general")
    draft: Mapped[str] = mapped_column(Text, default="")
    escalation: Mapped[str] = mapped_column(Text, default="")
    sources: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    current_job: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    updated_at: Mapped[int] = mapped_column(Integer, default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    author: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_claim", "state", "available_at", "lease_until"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[int] = mapped_column(Integer, default=now)
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str] = mapped_column(String(36), default="")
    error: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    finished_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    payload: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default="pending")
    expires_at: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class ReturnRequest(Base):
    __tablename__ = "return_requests"
    __table_args__ = (UniqueConstraint("org_id", "order_id"), UniqueConstraint("proposal_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"))
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    event: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
