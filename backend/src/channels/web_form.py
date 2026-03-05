"""
Web Form channel handler.

Endpoint: POST /channels/web-form/submit

Unlike Gmail/WhatsApp, web form submissions are processed synchronously —
the caller waits for the agent's response and receives it in the HTTP reply.
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from src.agent.core import process_inbound_message
from src.db.connection import get_db
from src.ingestion.normalizer import normalize_web_form

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/channels/web-form", tags=["web-form"])


# ─── Request / response models ────────────────────────────────────────────────

class WebFormSubmission(BaseModel):
    """Fields expected from the support web form."""

    email: EmailStr
    name: Optional[str] = Field(None, max_length=255)
    subject: Optional[str] = Field(None, max_length=300)
    category: Optional[str] = Field(
        "general",
        description="One of: general, billing, technical, feature_request, bug_report, feedback, other",
    )
    priority: Optional[str] = Field(
        "medium",
        description="One of: low, medium, high",
    )
    message: str = Field(..., min_length=5, max_length=5000)
    form_submission_id: Optional[str] = Field(
        None,
        description="Idempotency key set by the frontend to prevent duplicate submissions",
    )


class WebFormResponse(BaseModel):
    """The agent's response returned synchronously."""

    status: str
    ticket_id: Optional[str] = None
    message: str
    was_escalated: bool = False


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/ticket/{ticket_id}", tags=["web-form"])
async def get_ticket_status(ticket_id: str):
    """
    Get status and conversation history for a submitted ticket.
    Called by SupportForm.jsx to poll for agent reply.
    """
    from sqlalchemy import select
    from src.db.models import Ticket, Message

    async with get_db() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(Ticket).where(Ticket.display_id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Load messages
    async with get_db() as db:
        msgs_result = await db.execute(
            select(Message)
            .where(Message.ticket_id == ticket.id)
            .order_by(Message.created_at.asc())
        )
        messages = msgs_result.scalars().all()

    return {
        "ticket_id": ticket.display_id,
        "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "last_updated": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "messages": [
            {
                "body": m.body,
                "is_from_customer": m.is_from_customer,
                "channel": m.channel.value if hasattr(m.channel, "value") else str(m.channel),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post("/submit", response_model=WebFormResponse)
async def web_form_submit(submission: WebFormSubmission):
    """
    Process a web form support submission.

    Runs the full agent pipeline and returns the AI response synchronously.
    The frontend can display this response directly on the confirmation page
    or send it to the customer's email.
    """
    log.info(
        "web_form_received",
        email=submission.email,
        category=submission.category,
        subject=submission.subject,
    )

    normalized = normalize_web_form(submission.model_dump())

    async with get_db() as db:
        result = await process_inbound_message(normalized, db)

    if result is None:
        # Duplicate submission
        return WebFormResponse(
            status="duplicate",
            message="This form has already been submitted. Check your email for our reply.",
        )

    return WebFormResponse(
        status="escalated" if result.was_escalated else "resolved",
        ticket_id=result.ticket.display_id if result.ticket else None,
        message=result.response_text,
        was_escalated=result.was_escalated,
    )
