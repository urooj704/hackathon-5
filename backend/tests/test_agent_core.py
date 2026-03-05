"""
Tests for the agent core logic: process_inbound_message and run_agent.

Claude API calls are fully mocked so these tests run without credentials.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.db.models import ChannelEnum, PlanEnum
from src.ingestion.normalizer import NormalizedMessage


def _make_normalized(
    channel=ChannelEnum.EMAIL,
    body="My workflow is broken",
    email="user@example.com",
    phone=None,
    message_id="msg_001",
    thread_id="thread_001",
):
    return NormalizedMessage(
        channel=channel,
        body=body,
        timestamp=datetime.now(timezone.utc),
        customer_email=email,
        customer_phone=phone,
        customer_name="Test User",
        channel_message_id=message_id,
        channel_thread_id=thread_id,
    )


def _make_claude_response(text="Hi there! Here's how to fix that. How else can I help?", stop_reason="end_turn"):
    """Create a mock Anthropic API response."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    response = MagicMock()
    response.content = [block]
    response.stop_reason = stop_reason
    return response


def _make_tool_response(tool_name, tool_id, tool_input):
    """Create a mock tool-use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = tool_input
    return block


# ─── process_inbound_message ─────────────────────────────────────────────────

@pytest.mark.asyncio
class TestProcessInboundMessage:
    async def test_returns_none_for_duplicate(self, db, sample_customer):
        """If channel_message_id was already processed, returns None."""
        from src.db.crud import add_message, create_ticket
        from src.db.models import TicketUrgencyEnum

        # Create a ticket and message to simulate already-processed
        ticket = await create_ticket(
            db,
            customer_id=sample_customer.id,
            channel=ChannelEnum.EMAIL,
            urgency=TicketUrgencyEnum.LOW,
        )
        await add_message(
            db,
            ticket_id=ticket.id,
            channel=ChannelEnum.EMAIL,
            body="First message",
            is_from_customer=True,
            channel_message_id="duplicate_id",
        )
        await db.commit()

        msg = _make_normalized(message_id="duplicate_id")

        with patch("src.agent.core.resolve_customer", new_callable=AsyncMock) as mock_resolve, \
             patch("src.agent.core.crud.message_already_processed", new_callable=AsyncMock, return_value=True):
            from src.agent.core import process_inbound_message
            result = await process_inbound_message(msg, db)

        assert result is None

    async def test_saves_inbound_and_outbound_messages(self, db, sample_customer):
        """After a successful run, both inbound and outbound messages are persisted."""
        from src.agent.core import process_inbound_message, AgentResult
        from src.db.models import TicketUrgencyEnum

        mock_ticket = MagicMock()
        mock_ticket.id = 1
        mock_ticket.display_id = "TKT-00001"

        mock_result = AgentResult(
            response_text="Here's the fix. How else can I help?",
            ticket=mock_ticket,
            was_escalated=False,
        )

        msg = _make_normalized(message_id="new_msg_001")

        with patch("src.agent.core.resolve_customer", new_callable=AsyncMock, return_value=sample_customer), \
             patch("src.agent.core.crud.message_already_processed", new_callable=AsyncMock, return_value=False), \
             patch("src.agent.core._find_open_ticket", new_callable=AsyncMock, return_value=None), \
             patch("src.agent.core.run_agent", new_callable=AsyncMock, return_value=mock_result), \
             patch("src.agent.core.crud.add_message", new_callable=AsyncMock) as mock_add:

            result = await process_inbound_message(msg, db)

        assert result is not None
        assert result.response_text == "Here's the fix. How else can I help?"
        # add_message called twice: inbound + outbound
        assert mock_add.call_count == 2


# ─── run_agent ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRunAgent:
    async def test_single_turn_no_tools(self, db, sample_customer):
        """Agent returns response directly when Claude uses no tools."""
        from src.agent.core import run_agent

        mock_response = _make_claude_response("Go to Settings → Integrations. How else can I help?")

        with patch("src.agent.core.crud.get_recent_tickets_for_customer", new_callable=AsyncMock, return_value=[]), \
             patch("anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            result = await run_agent(
                db=db,
                customer=sample_customer,
                channel=ChannelEnum.EMAIL,
                message_body="How do I connect HubSpot?",
            )

        assert "Settings" in result.response_text or "help" in result.response_text.lower()
        assert result.was_escalated is False

    async def test_escalation_returns_template(self, db, sample_customer):
        """When the agent escalates, the canonical escalation template is returned."""
        from src.agent.core import run_agent, AgentContext

        # First Claude call returns a tool_use (escalate), second returns text
        tool_block = _make_tool_response(
            "escalate",
            "tool_001",
            {
                "tier": "tier_1",
                "reason": "Legal threat",
                "route_to": "legal@flowforge.io",
            },
        )
        tool_response = MagicMock()
        tool_response.content = [tool_block]
        tool_response.stop_reason = "tool_use"

        final_response = _make_claude_response("I've flagged this for our team.")

        async def mock_execute_tool(name, input_, ctx):
            ctx.is_escalated = True
            from src.db.models import EscalationTierEnum
            ctx.escalation_tier = EscalationTierEnum.TIER_1
            ctx.escalation_route = "legal@flowforge.io"
            return "Escalation logged."

        with patch("src.agent.core.crud.get_recent_tickets_for_customer", new_callable=AsyncMock, return_value=[]), \
             patch("src.agent.core.execute_tool", side_effect=mock_execute_tool), \
             patch("anthropic.AsyncAnthropic") as mock_anthropic:

            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                side_effect=[tool_response, final_response]
            )

            result = await run_agent(
                db=db,
                customer=sample_customer,
                channel=ChannelEnum.EMAIL,
                message_body="I'm going to sue you",
            )

        assert result.was_escalated is True
        # Should be the canonical escalation template, not Claude's raw text
        assert "specialist" in result.response_text.lower() or "team" in result.response_text.lower()

    async def test_web_form_channel_uses_correct_prompt(self, db, sample_customer):
        """Web form channel uses the web form prompt addendum."""
        from src.agent.core import run_agent
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt(ChannelEnum.WEB_FORM)
        assert "Web Form Channel Rules" in prompt
        assert "Hi [Name]," in prompt

    async def test_whatsapp_channel_prompt_no_greeting(self, db, sample_customer):
        """WhatsApp prompt forbids formal greetings."""
        from src.agent.prompts import get_system_prompt

        prompt = get_system_prompt(ChannelEnum.WHATSAPP)
        assert "No formal greeting" in prompt
        assert "Maximum 2-3 short sentences" in prompt


# ─── _find_open_ticket ───────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestFindOpenTicket:
    async def test_web_form_always_returns_none(self, db, sample_customer):
        from src.agent.core import _find_open_ticket

        msg = _make_normalized(channel=ChannelEnum.WEB_FORM)
        result = await _find_open_ticket(db, sample_customer, msg)
        assert result is None

    async def test_no_open_tickets_returns_none(self, db, sample_customer):
        from src.agent.core import _find_open_ticket

        msg = _make_normalized(channel=ChannelEnum.EMAIL)

        with patch("src.agent.core.crud.get_open_tickets_for_customer", new_callable=AsyncMock, return_value=[]):
            result = await _find_open_ticket(db, sample_customer, msg)

        assert result is None
