"""
Core agent loop — AgentContext, run_agent(), and the full inbound message pipeline.

Flow:
  normalize → identity → find/create ticket → run agent (tool loop) → save messages
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass, field
from typing import Optional, List

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import crud
from src.db.models import (
    ChannelEnum,
    Customer,
    Ticket,
    EscalationTierEnum,
)
from src.agent.prompts import (
    get_system_prompt,
    format_customer_context,
    format_conversation_history,
)
from src.agent.tools import TOOLS, execute_tool
from src.ingestion.identity import resolve_customer
from src.ingestion.normalizer import NormalizedMessage

log = structlog.get_logger(__name__)
settings = get_settings()

# ─── Escalation acknowledgement templates ────────────────────────────────────

_ESCALATION_MSG = {
    ChannelEnum.EMAIL: (
        "Hi {name},\n\n"
        "I've flagged your message for our specialist team — they'll follow up with you shortly.\n\n"
        "Best,\nFlowForge Support"
    ),
    ChannelEnum.WHATSAPP: "I'm looping in our team on this one — you'll hear back shortly. 👋",
    ChannelEnum.WEB_FORM: (
        "Hi {name},\n\n"
        "I've passed this to the right team and you'll hear back soon.\n\nThanks"
    ),
}


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """
    Mutable state passed through the agentic loop and into every tool handler.
    Tool handlers mutate this object to signal state changes back to run_agent().
    """
    db: AsyncSession
    customer: Customer
    channel: ChannelEnum
    current_ticket: Optional[Ticket] = None
    is_escalated: bool = False
    escalation_tier: Optional[EscalationTierEnum] = None
    escalation_route: Optional[str] = None


@dataclass
class AgentResult:
    """What the agent produces for a single inbound message."""
    response_text: str
    ticket: Optional[Ticket]
    was_escalated: bool
    escalation_tier: Optional[str] = None
    escalation_route: Optional[str] = None


# ─── Main agent loop ──────────────────────────────────────────────────────────

async def run_agent(
    db: AsyncSession,
    customer: Customer,
    channel: ChannelEnum,
    message_body: str,
    existing_ticket: Optional[Ticket] = None,
) -> AgentResult:
    """
    Run a full Claude agentic loop for one customer message.

    The agent may call tools (search_docs, create_ticket, update_ticket,
    escalate, check_status_page) in multiple rounds before producing a
    final text response.
    """
    context = AgentContext(
        db=db,
        customer=customer,
        channel=channel,
        current_ticket=existing_ticket,
    )

    # ── Build context blocks ──────────────────────────────────────────────────
    recent_tickets = await crud.get_recent_tickets_for_customer(
        db, customer.id, limit=settings.max_history_tickets
    )
    customer_ctx = format_customer_context(customer, recent_tickets)

    conversation_ctx = ""
    if existing_ticket:
        recent_msgs = await crud.get_recent_messages_for_ticket(
            db, existing_ticket.id, limit=settings.max_history_messages
        )
        conversation_ctx = format_conversation_history(recent_msgs)

    context_block = "\n\n".join(filter(None, [customer_ctx, conversation_ctx]))
    full_user_msg = (
        f"{context_block}\n\n---\n\n## New Customer Message\n{message_body}"
        if context_block
        else message_body
    )

    # ── Claude client + initial messages ─────────────────────────────────────
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages: List[dict] = [{"role": "user", "content": full_user_msg}]
    system_prompt = get_system_prompt(channel)

    # ── Agentic tool loop ─────────────────────────────────────────────────────
    max_iterations = 10
    for iteration in range(1, max_iterations + 1):
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        log.info(
            "agent_turn",
            iteration=iteration,
            stop_reason=response.stop_reason,
            customer_id=customer.id,
            channel=channel.value,
        )

        # Separate text from tool-use blocks
        text_blocks = [b for b in response.content if b.type == "text"]
        tool_blocks = [b for b in response.content if b.type == "tool_use"]

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        # No tool calls → final response
        if response.stop_reason == "end_turn" or not tool_blocks:
            final_text = "\n".join(b.text for b in text_blocks).strip()
            return _build_result(context, customer, channel, final_text)

        # Execute all tool calls
        tool_results = []
        for tool_block in tool_blocks:
            log.info(
                "tool_call",
                tool=tool_block.name,
                customer_id=customer.id,
            )
            result_str = await execute_tool(tool_block.name, tool_block.input, context)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result_str,
                }
            )

        messages.append({"role": "user", "content": tool_results})

        # After escalation tool fires, get one more Claude turn for the reply
        # then return the canonical escalation acknowledgement
        if context.is_escalated:
            # One final Claude turn (may produce empathetic closing text)
            await client.messages.create(
                model=settings.claude_model,
                max_tokens=256,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
            return _build_result(context, customer, channel, "")

    # Max iterations hit — safe fallback
    log.warning("agent_max_iterations", customer_id=customer.id)
    return _build_result(
        context,
        customer,
        channel,
        "Let me look into this further and get back to you. How else can I help?",
    )


def _build_result(
    context: AgentContext,
    customer: Customer,
    channel: ChannelEnum,
    ai_text: str,
) -> AgentResult:
    """Build AgentResult, substituting escalation template when needed."""
    if context.is_escalated:
        first_name = (customer.name or "there").split()[0]
        template = _ESCALATION_MSG.get(channel, _ESCALATION_MSG[ChannelEnum.WEB_FORM])
        response_text = (
            template.format(name=first_name) if "{name}" in template else template
        )
    else:
        response_text = ai_text or "How else can I help?"

    return AgentResult(
        response_text=response_text,
        ticket=context.current_ticket,
        was_escalated=context.is_escalated,
        escalation_tier=(
            context.escalation_tier.value if context.escalation_tier else None
        ),
        escalation_route=context.escalation_route,
    )


# ─── Full inbound pipeline ────────────────────────────────────────────────────

async def process_inbound_message(
    normalized_msg: NormalizedMessage,
    db: AsyncSession,
) -> Optional[AgentResult]:
    """
    Full pipeline for one inbound message (any channel):
      1. Dedup check
      2. Resolve customer identity
      3. Find open ticket for this conversation thread
      4. Run agent
      5. Persist inbound + outbound messages
      6. Return AgentResult (caller sends the response via channel)

    Returns None if the message is a duplicate.
    """
    # 1. Dedup
    if normalized_msg.channel_message_id:
        if await crud.message_already_processed(db, normalized_msg.channel_message_id):
            log.info(
                "duplicate_message_skipped",
                channel_message_id=normalized_msg.channel_message_id,
            )
            return None

    # 2. Identity resolution
    customer = await resolve_customer(db, normalized_msg)

    # 3. Find open ticket for this thread
    existing_ticket = await _find_open_ticket(db, customer, normalized_msg)

    # 4. Run agent
    result = await run_agent(
        db=db,
        customer=customer,
        channel=normalized_msg.channel,
        message_body=normalized_msg.body,
        existing_ticket=existing_ticket,
    )

    # 5. Persist messages (agent may have created the ticket internally)
    if result.ticket:
        attachment_meta = (
            [
                {
                    "filename": a.filename,
                    "mime_type": a.mime_type,
                    "size_bytes": a.size_bytes,
                }
                for a in normalized_msg.attachments
            ]
            or None
        )

        # Save the inbound customer message
        await crud.add_message(
            db=db,
            ticket_id=result.ticket.id,
            channel=normalized_msg.channel,
            body=normalized_msg.body,
            is_from_customer=True,
            channel_message_id=normalized_msg.channel_message_id,
            has_attachments=normalized_msg.has_attachments,
            attachment_metadata=attachment_meta,
        )

        # Save the agent's outbound response
        await crud.add_message(
            db=db,
            ticket_id=result.ticket.id,
            channel=normalized_msg.channel,
            body=result.response_text,
            is_from_customer=False,
            is_ai_generated=True,
        )

    return result


async def _find_open_ticket(
    db: AsyncSession,
    customer: Customer,
    msg: NormalizedMessage,
) -> Optional[Ticket]:
    """
    Find an open ticket that belongs to this conversation thread.

    Strategy:
    - Web form: always None (each submission = new ticket)
    - Gmail: most recent open EMAIL ticket for this customer
      (Gmail threads are tracked via raw metadata in channel_thread_id)
    - WhatsApp: most recent open WHATSAPP ticket within the last 24 h
    """
    if msg.channel == ChannelEnum.WEB_FORM:
        return None

    open_tickets = await crud.get_open_tickets_for_customer(db, customer.id, limit=10)
    if not open_tickets:
        return None

    # Filter to same-channel tickets
    same_channel = [t for t in open_tickets if t.origin_channel == msg.channel]

    if not same_channel:
        return None

    # For Gmail: match by thread ID stored in the first message's channel_message_id
    if msg.channel == ChannelEnum.EMAIL and msg.channel_thread_id:
        for ticket in same_channel:
            for message in ticket.messages:
                stored = message.channel_message_id or ""
                # We store Gmail messages as "thread_id:message_id"
                if stored.startswith(f"{msg.channel_thread_id}:"):
                    return ticket

    # WhatsApp: return most recent open ticket (same conversation thread)
    if msg.channel == ChannelEnum.WHATSAPP:
        return same_channel[0]

    return None
