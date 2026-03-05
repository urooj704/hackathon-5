"""
SQLAlchemy ORM models for FlowForge Customer Success Agent.

Tables:
  customers       — unified customer record (cross-channel identity)
  tickets         — support tickets (one per issue, linked to customer)
  messages        — individual messages within a ticket (any channel)
  escalations     — escalation events tied to a ticket
  doc_chunks      — knowledge base chunks with pgvector embeddings
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ─── Enums ────────────────────────────────────────────────────────────────────

class ChannelEnum(str, PyEnum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class TicketStatusEnum(str, PyEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketUrgencyEnum(str, PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SentimentEnum(str, PyEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    ANXIOUS = "anxious"
    ANGRY = "angry"
    FURIOUS = "furious"


class EscalationTierEnum(str, PyEnum):
    TIER_1 = "tier_1"   # Immediate — no AI resolution attempt
    TIER_2 = "tier_2"   # AI responds + flags for human review
    TIER_3 = "tier_3"   # Flag only, no immediate action


class PlanEnum(str, PyEnum):
    STARTER = "starter"
    GROWTH = "growth"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    TRIAL = "trial"
    UNKNOWN = "unknown"


# ─── Base ─────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── Customer ─────────────────────────────────────────────────────────────────

class Customer(Base):
    """
    Unified customer record — created once, linked across all channels.
    A single customer may contact us via email, WhatsApp, and web form.
    The identity resolver matches on email (primary) or phone (secondary).
    """
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Identity fields — at least one must be present
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True, index=True)

    # Profile
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    plan: Mapped[PlanEnum] = mapped_column(
        Enum(PlanEnum, name="plan_enum"), default=PlanEnum.UNKNOWN
    )
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gdpr_region: Mapped[bool] = mapped_column(Boolean, default=False)  # True = EU

    # Relationship metadata
    is_enterprise: Mapped[bool] = mapped_column(Boolean, default=False)
    csm_assigned: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Churn / health signals
    churn_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    lifetime_tickets: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket", back_populates="customer", order_by="Ticket.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} email={self.email} phone={self.phone}>"


# ─── Ticket ───────────────────────────────────────────────────────────────────

class Ticket(Base):
    """
    One ticket = one issue/conversation thread.
    A ticket can span multiple channels (e.g., started by email, followed up on WhatsApp).
    The ticket stays open until the issue is resolved regardless of channel switches.
    """
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )

    # Display ID (human-readable, e.g., TKT-00123)
    display_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    # Classification
    status: Mapped[TicketStatusEnum] = mapped_column(
        Enum(TicketStatusEnum, name="ticket_status_enum"), default=TicketStatusEnum.OPEN
    )
    urgency: Mapped[TicketUrgencyEnum] = mapped_column(
        Enum(TicketUrgencyEnum, name="ticket_urgency_enum"), default=TicketUrgencyEnum.MEDIUM
    )
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # e.g. "technical_support", "billing_dispute", "how_to", "escalation"

    # Channel where the ticket originated
    origin_channel: Mapped[ChannelEnum] = mapped_column(
        Enum(ChannelEnum, name="channel_enum")
    )

    # Summary (AI-generated, updated on each meaningful new message)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_suggested_resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Sentiment trend
    latest_sentiment: Mapped[Optional[SentimentEnum]] = mapped_column(
        Enum(SentimentEnum, name="sentiment_enum"), nullable=True
    )

    # Assignment
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # human agent email if escalated

    # Resolution
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="tickets")
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="ticket", order_by="Message.created_at.asc()"
    )
    escalations: Mapped[List["Escalation"]] = relationship(
        "Escalation", back_populates="ticket"
    )

    def __repr__(self) -> str:
        return f"<Ticket {self.display_id} status={self.status} urgency={self.urgency}>"


# ─── Message ──────────────────────────────────────────────────────────────────

class Message(Base):
    """
    Individual message within a ticket.
    Can be from the customer (inbound) or from the agent (outbound — AI or human).
    Tracks which channel each specific message came through.
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )

    # Direction
    is_from_customer: Mapped[bool] = mapped_column(Boolean, default=True)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Channel this specific message arrived/was sent on
    channel: Mapped[ChannelEnum] = mapped_column(
        Enum(ChannelEnum, name="channel_enum")
    )

    # Content
    body: Mapped[str] = mapped_column(Text)
    # Channel-specific message identifiers (for threading/dedup)
    channel_message_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # e.g., Gmail message ID, WhatsApp message SID, web form submission ID

    # Attachment metadata (we don't store binary — just metadata)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    attachment_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # [{"filename": "screenshot.png", "mime_type": "image/png", "size_bytes": 204800}]

    # AI analysis of this specific message
    detected_sentiment: Mapped[Optional[SentimentEnum]] = mapped_column(
        Enum(SentimentEnum, name="sentiment_enum"), nullable=True
    )
    detected_intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # -1.0 (very negative) to 1.0 (very positive)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_ticket_created", "ticket_id", "created_at"),
        Index("ix_messages_channel_msg_id", "channel_message_id"),
    )

    def __repr__(self) -> str:
        direction = "IN" if self.is_from_customer else "OUT"
        return f"<Message id={self.id} [{direction}] channel={self.channel}>"


# ─── Escalation ───────────────────────────────────────────────────────────────

class Escalation(Base):
    """
    Records every escalation event — who triggered it, why, and where it was routed.
    Escalations are tied to tickets, not individual messages.
    """
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )

    tier: Mapped[EscalationTierEnum] = mapped_column(
        Enum(EscalationTierEnum, name="escalation_tier_enum")
    )
    reason: Mapped[str] = mapped_column(String(500))
    # Human-readable reason, e.g. "Customer threatened chargeback (TKT-010)"

    trigger_keywords: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # ["chargeback", "dispute", "my bank"] — keywords that fired the rule

    routed_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # email of team/person it was routed to: "billing@flowforge.io"

    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="escalations")

    def __repr__(self) -> str:
        return f"<Escalation ticket={self.ticket_id} tier={self.tier} routed_to={self.routed_to}>"


# ─── DocChunk (Knowledge Base) ────────────────────────────────────────────────

class DocChunk(Base):
    """
    Chunked knowledge base entries with pgvector embeddings.
    Loaded from product-docs.md at startup; re-indexed when docs change.
    """
    __tablename__ = "doc_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source tracking
    source_file: Mapped[str] = mapped_column(String(255))
    # e.g., "product-docs.md"
    section_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # e.g., "3.1 Gmail / Google Workspace"

    # Content
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    # position within the document

    # Vector embedding (1536 dims for text-embedding-3-small)
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(1536), nullable=True
    )

    # Metadata for filtering
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # e.g., ["billing", "gmail", "error_handling"]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_doc_chunks_embedding_cosine",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 50},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<DocChunk id={self.id} section={self.section_title} chunk={self.chunk_index}>"
