"""
CRUD helpers for all DB operations.
All functions are async and accept an AsyncSession.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    Customer,
    Ticket,
    Message,
    Escalation,
    ChannelEnum,
    TicketStatusEnum,
    TicketUrgencyEnum,
    SentimentEnum,
    EscalationTierEnum,
    PlanEnum,
)


# ─── Customer CRUD ────────────────────────────────────────────────────────────

async def get_customer_by_email(db: AsyncSession, email: str) -> Optional[Customer]:
    result = await db.execute(
        select(Customer).where(Customer.email == email.lower().strip())
    )
    return result.scalar_one_or_none()


async def get_customer_by_phone(db: AsyncSession, phone: str) -> Optional[Customer]:
    result = await db.execute(
        select(Customer).where(Customer.phone == phone.strip())
    )
    return result.scalar_one_or_none()


async def get_customer_by_id(db: AsyncSession, customer_id: int) -> Optional[Customer]:
    result = await db.execute(
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.tickets))
    )
    return result.scalar_one_or_none()


async def create_customer(
    db: AsyncSession,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    name: Optional[str] = None,
    plan: PlanEnum = PlanEnum.UNKNOWN,
) -> Customer:
    customer = Customer(
        email=email.lower().strip() if email else None,
        phone=phone.strip() if phone else None,
        name=name,
        plan=plan,
    )
    db.add(customer)
    await db.flush()  # get ID without committing
    return customer


async def update_customer(
    db: AsyncSession,
    customer_id: int,
    **kwargs,
) -> Optional[Customer]:
    await db.execute(
        update(Customer).where(Customer.id == customer_id).values(**kwargs)
    )
    return await get_customer_by_id(db, customer_id)


async def link_customer_phone_to_email(
    db: AsyncSession,
    customer: Customer,
    phone: str,
) -> Customer:
    """
    Link a WhatsApp phone number to an existing customer record (identified by email).
    Called when a customer provides their email during a WhatsApp conversation.
    """
    customer.phone = phone.strip()
    await db.flush()
    return customer


# ─── Ticket CRUD ──────────────────────────────────────────────────────────────

async def _generate_display_id(db: AsyncSession) -> str:
    """Generate next TKT-XXXXX display ID."""
    result = await db.execute(select(func.count(Ticket.id)))
    count = result.scalar_one() or 0
    return f"TKT-{(count + 1):05d}"


async def create_ticket(
    db: AsyncSession,
    customer_id: int,
    channel: ChannelEnum,
    intent: Optional[str] = None,
    urgency: TicketUrgencyEnum = TicketUrgencyEnum.MEDIUM,
    summary: Optional[str] = None,
) -> Ticket:
    display_id = await _generate_display_id(db)
    ticket = Ticket(
        customer_id=customer_id,
        display_id=display_id,
        origin_channel=channel,
        intent=intent,
        urgency=urgency,
        summary=summary,
        status=TicketStatusEnum.OPEN,
    )
    db.add(ticket)
    await db.flush()
    return ticket


async def get_ticket_by_id(db: AsyncSession, ticket_id: int) -> Optional[Ticket]:
    result = await db.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.messages),
            selectinload(Ticket.escalations),
            selectinload(Ticket.customer),
        )
    )
    return result.scalar_one_or_none()


async def get_open_tickets_for_customer(
    db: AsyncSession,
    customer_id: int,
    limit: int = 5,
) -> List[Ticket]:
    result = await db.execute(
        select(Ticket)
        .where(
            Ticket.customer_id == customer_id,
            Ticket.status.not_in([TicketStatusEnum.RESOLVED, TicketStatusEnum.CLOSED]),
        )
        .options(selectinload(Ticket.messages))
        .order_by(Ticket.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_recent_tickets_for_customer(
    db: AsyncSession,
    customer_id: int,
    limit: int = 3,
) -> List[Ticket]:
    """Fetch last N tickets (any status) for loading historical context."""
    result = await db.execute(
        select(Ticket)
        .where(Ticket.customer_id == customer_id)
        .options(selectinload(Ticket.messages))
        .order_by(Ticket.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_ticket(
    db: AsyncSession,
    ticket_id: int,
    **kwargs,
) -> None:
    await db.execute(
        update(Ticket).where(Ticket.id == ticket_id).values(**kwargs)
    )


async def resolve_ticket(
    db: AsyncSession,
    ticket_id: int,
    resolution_notes: Optional[str] = None,
) -> None:
    await db.execute(
        update(Ticket)
        .where(Ticket.id == ticket_id)
        .values(
            status=TicketStatusEnum.RESOLVED,
            resolved_at=datetime.now(timezone.utc),
            resolution_notes=resolution_notes,
        )
    )


# ─── Message CRUD ─────────────────────────────────────────────────────────────

async def add_message(
    db: AsyncSession,
    ticket_id: int,
    channel: ChannelEnum,
    body: str,
    is_from_customer: bool,
    is_ai_generated: bool = False,
    channel_message_id: Optional[str] = None,
    detected_sentiment: Optional[SentimentEnum] = None,
    detected_intent: Optional[str] = None,
    sentiment_score: Optional[float] = None,
    has_attachments: bool = False,
    attachment_metadata: Optional[list] = None,
) -> Message:
    msg = Message(
        ticket_id=ticket_id,
        channel=channel,
        body=body,
        is_from_customer=is_from_customer,
        is_ai_generated=is_ai_generated,
        channel_message_id=channel_message_id,
        detected_sentiment=detected_sentiment,
        detected_intent=detected_intent,
        sentiment_score=sentiment_score,
        has_attachments=has_attachments,
        attachment_metadata=attachment_metadata,
    )
    db.add(msg)
    await db.flush()
    return msg


async def get_recent_messages_for_ticket(
    db: AsyncSession,
    ticket_id: int,
    limit: int = 10,
) -> List[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.ticket_id == ticket_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    # Return in chronological order
    return list(reversed(result.scalars().all()))


async def message_already_processed(
    db: AsyncSession,
    channel_message_id: str,
) -> bool:
    """Deduplication check — avoid processing the same webhook twice."""
    result = await db.execute(
        select(Message.id).where(Message.channel_message_id == channel_message_id)
    )
    return result.scalar_one_or_none() is not None


# ─── Escalation CRUD ──────────────────────────────────────────────────────────

async def create_escalation(
    db: AsyncSession,
    ticket_id: int,
    tier: EscalationTierEnum,
    reason: str,
    routed_to: Optional[str] = None,
    trigger_keywords: Optional[list] = None,
) -> Escalation:
    esc = Escalation(
        ticket_id=ticket_id,
        tier=tier,
        reason=reason,
        routed_to=routed_to,
        trigger_keywords=trigger_keywords,
    )
    db.add(esc)
    await db.flush()
    return esc
