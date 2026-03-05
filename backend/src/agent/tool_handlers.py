"""
Tool handler implementations.
Each handler receives (tool_input, context) and returns a string result for Claude.
"""

from typing import TYPE_CHECKING, Any

import httpx
import structlog

from src.db import crud
from src.db.models import (
    ChannelEnum,
    EscalationTierEnum,
    TicketStatusEnum,
    TicketUrgencyEnum,
)
from src.knowledge.retriever import format_docs_for_prompt, search_docs

if TYPE_CHECKING:
    from src.agent.core import AgentContext

log = structlog.get_logger(__name__)


async def handle_search_docs(tool_input: dict[str, Any], context: "AgentContext") -> str:
    query = tool_input.get("query", "")
    if not query:
        return "Error: search query was empty."

    chunks = await search_docs(context.db, query, top_k=4)

    if not chunks:
        return (
            "No relevant documentation found for that query. "
            "You may need to ask a clarifying question or escalate."
        )

    return format_docs_for_prompt(chunks)


async def handle_create_ticket(tool_input: dict[str, Any], context: "AgentContext") -> str:
    intent = tool_input.get("intent", "other")
    urgency_str = tool_input.get("urgency", "medium")
    summary = tool_input.get("summary", "")

    urgency_map = {
        "low": TicketUrgencyEnum.LOW,
        "medium": TicketUrgencyEnum.MEDIUM,
        "high": TicketUrgencyEnum.HIGH,
        "critical": TicketUrgencyEnum.CRITICAL,
    }
    urgency = urgency_map.get(urgency_str, TicketUrgencyEnum.MEDIUM)

    ticket = await crud.create_ticket(
        db=context.db,
        customer_id=context.customer.id,
        channel=context.channel,
        intent=intent,
        urgency=urgency,
        summary=summary,
    )

    # Update in-memory context so subsequent tool calls use this ticket
    context.current_ticket = ticket

    # Increment customer lifetime ticket count
    await crud.update_customer(
        context.db,
        context.customer.id,
        lifetime_tickets=context.customer.lifetime_tickets + 1,
    )

    log.info(
        "ticket_created",
        ticket_id=ticket.id,
        display_id=ticket.display_id,
        customer_id=context.customer.id,
    )

    return (
        f"Ticket created successfully. "
        f"Display ID: {ticket.display_id} | Intent: {intent} | Urgency: {urgency_str} | "
        f"Summary: {summary}"
    )


async def handle_update_ticket(tool_input: dict[str, Any], context: "AgentContext") -> str:
    if not context.current_ticket:
        return "No active ticket to update. Create a ticket first."

    updates = {}
    status_map = {
        "open": TicketStatusEnum.OPEN,
        "in_progress": TicketStatusEnum.IN_PROGRESS,
        "waiting_customer": TicketStatusEnum.WAITING_CUSTOMER,
        "escalated": TicketStatusEnum.ESCALATED,
        "resolved": TicketStatusEnum.RESOLVED,
    }

    if "status" in tool_input:
        updates["status"] = status_map.get(tool_input["status"], TicketStatusEnum.IN_PROGRESS)

    urgency_map = {
        "low": TicketUrgencyEnum.LOW,
        "medium": TicketUrgencyEnum.MEDIUM,
        "high": TicketUrgencyEnum.HIGH,
        "critical": TicketUrgencyEnum.CRITICAL,
    }
    if "urgency" in tool_input:
        updates["urgency"] = urgency_map.get(tool_input["urgency"], TicketUrgencyEnum.MEDIUM)

    if "summary" in tool_input:
        updates["summary"] = tool_input["summary"]

    if "resolution_notes" in tool_input:
        updates["resolution_notes"] = tool_input["resolution_notes"]

    if updates:
        await crud.update_ticket(context.db, context.current_ticket.id, **updates)
        log.info(
            "ticket_updated",
            ticket_id=context.current_ticket.id,
            updates=list(updates.keys()),
        )

    return f"Ticket {context.current_ticket.display_id} updated: {list(updates.keys())}"


async def handle_escalate(tool_input: dict[str, Any], context: "AgentContext") -> str:
    if not context.current_ticket:
        # Auto-create a ticket if one doesn't exist yet
        ticket = await crud.create_ticket(
            db=context.db,
            customer_id=context.customer.id,
            channel=context.channel,
            intent="escalation",
            urgency=TicketUrgencyEnum.HIGH,
            summary="Escalation — ticket auto-created during escalation",
        )
        context.current_ticket = ticket

    tier_map = {
        "tier_1": EscalationTierEnum.TIER_1,
        "tier_2": EscalationTierEnum.TIER_2,
        "tier_3": EscalationTierEnum.TIER_3,
    }
    tier = tier_map.get(tool_input.get("tier", "tier_2"), EscalationTierEnum.TIER_2)
    reason = tool_input.get("reason", "No reason provided")
    route_to = tool_input.get("route_to", "human_queue")
    trigger_keywords = tool_input.get("trigger_keywords", [])

    escalation = await crud.create_escalation(
        db=context.db,
        ticket_id=context.current_ticket.id,
        tier=tier,
        reason=reason,
        routed_to=route_to,
        trigger_keywords=trigger_keywords,
    )

    # Update ticket status to escalated
    await crud.update_ticket(
        context.db,
        context.current_ticket.id,
        status=TicketStatusEnum.ESCALATED,
    )

    # Mark in context so the response generator knows to use escalation template
    context.is_escalated = True
    context.escalation_tier = tier
    context.escalation_route = route_to

    log.info(
        "ticket_escalated",
        ticket_id=context.current_ticket.id,
        tier=tier.value,
        route_to=route_to,
        reason=reason,
    )

    return (
        f"Escalation logged. "
        f"Tier: {tier.value} | Routed to: {route_to} | Reason: {reason} | "
        f"Escalation ID: {escalation.id}"
    )


async def handle_check_status_page(tool_input: dict[str, Any], context: "AgentContext") -> str:
    """
    Check status.flowforge.io for active incidents.
    In production: parse the real status page API.
    For demo: returns a simulated response.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Statuspage.io has a public API — many status pages use this format
            resp = await client.get(
                "https://status.flowforge.io/api/v2/status.json",
                follow_redirects=True,
            )
            if resp.status_code == 200:
                data = resp.json()
                indicator = data.get("status", {}).get("indicator", "unknown")
                description = data.get("status", {}).get("description", "Unknown status")

                if indicator == "none":
                    return "Status page shows ALL SYSTEMS OPERATIONAL. No active incidents."
                else:
                    return (
                        f"Status page shows: {description} (indicator: {indicator}). "
                        f"There may be an active incident — advise customer to check status.flowforge.io for live updates."
                    )
    except Exception:
        pass

    # Fallback for demo / when status page isn't reachable
    return (
        "Status page check: Unable to reach status.flowforge.io automatically. "
        "Advise the customer to check https://status.flowforge.io directly for live status. "
        "If workflows are failing broadly, it may indicate a platform incident."
    )
