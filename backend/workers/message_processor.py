"""
Unified Message Processor — FlowForge Customer Success FTE

Consumes inbound messages from ALL channels via Kafka and routes them
through the agent pipeline. Handles:
  - Customer identity resolution
  - Conversation context loading
  - Agent execution (OpenAI Agents SDK or Anthropic fallback)
  - Response delivery per channel
  - Metrics publishing
  - Error handling + DLQ routing

Run:
    python workers/message_processor.py

Or via Docker:
    docker run -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 fte-worker
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka_client import FTEKafkaConsumer, FTEKafkaProducer, TOPICS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("fte.worker")


# ─── Channel definitions ──────────────────────────────────────────────────────

SUPPORTED_CHANNELS = {"email", "whatsapp", "web_form"}


# ─── Unified Message Processor ────────────────────────────────────────────────

class UnifiedMessageProcessor:
    """
    Process incoming messages from all channels through the FTE agent.

    Architecture:
        Kafka consumer → identity resolve → load history → run agent
        → store response → deliver via channel → publish metrics
    """

    def __init__(self):
        self.producer = FTEKafkaProducer()
        self._db_pool = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize connections and start consuming."""
        await self.producer.start()
        await self._init_db()

        consumer = FTEKafkaConsumer(
            topics=[TOPICS["tickets_incoming"]],
            group_id="fte-message-processor",
        )
        await consumer.start()

        logger.info(
            "Message processor started — listening on %s",
            TOPICS["tickets_incoming"],
        )
        await consumer.consume(self.process_message, producer=self.producer)

    async def _init_db(self) -> None:
        """Initialize DB connection pool."""
        try:
            import asyncpg
            dsn = os.getenv("DATABASE_URL", "postgresql://localhost/fte_db")
            self._db_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
            logger.info("DB pool initialized")
        except Exception as exc:
            logger.warning(f"DB pool not available: {exc} — running in mock mode")
            self._db_pool = None

    # ── Main message handler ──────────────────────────────────────────────────

    async def process_message(self, topic: str, message: dict) -> None:
        """
        Process a single inbound message from any channel.

        Steps:
            1. Validate channel
            2. Resolve customer identity
            3. Get/create conversation
            4. Store inbound message
            5. Load conversation history
            6. Run agent
            7. Store + deliver response
            8. Publish metrics
        """
        start_time = datetime.now(timezone.utc)
        channel = message.get("channel", "")

        if channel not in SUPPORTED_CHANNELS:
            logger.warning(f"Unknown channel: {channel} — skipping")
            return

        logger.info(f"Processing {channel} message from {message.get('customer_email') or message.get('customer_phone', 'unknown')}")

        try:
            # 1. Resolve customer
            customer_id = await self.resolve_customer(message)

            # 2. Get or create conversation/ticket
            ticket_id = await self.get_or_create_ticket(customer_id, channel, message)

            # 3. Store inbound message
            await self.store_message(
                ticket_id=ticket_id,
                channel=channel,
                direction="inbound",
                content=message.get("body") or message.get("content", ""),
                channel_message_id=message.get("channel_message_id"),
            )

            # 4. Load conversation history
            history = await self.load_history(ticket_id)

            # 5. Run agent
            agent_result = await self.run_agent(
                message=message,
                customer_id=customer_id,
                ticket_id=ticket_id,
                channel=channel,
                history=history,
            )

            # 6. Store + deliver response
            if agent_result.get("response_text"):
                await self.store_message(
                    ticket_id=ticket_id,
                    channel=channel,
                    direction="outbound",
                    content=agent_result["response_text"],
                )
                await self.deliver_response(channel, message, agent_result)

            # 7. Publish metrics
            latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            await self.producer.publish_metric(
                "message.processing_latency_ms",
                latency_ms,
                tags={
                    "channel": channel,
                    "escalated": str(agent_result.get("escalated", False)),
                },
            )

            logger.info(f"Processed {channel} message in {latency_ms:.0f}ms | escalated={agent_result.get('escalated')}")

        except Exception as exc:
            logger.error(f"Error processing message: {exc}", exc_info=True)
            await self._handle_error(message, exc)

    # ── Customer identity ─────────────────────────────────────────────────────

    async def resolve_customer(self, message: dict) -> str:
        """Resolve or create customer from message identifiers."""
        email = message.get("customer_email")
        phone = message.get("customer_phone")
        name = message.get("customer_name", "")

        if self._db_pool:
            return await self._resolve_customer_db(email, phone, name)

        # Mock: use email or phone as ID
        return email or phone or f"anon-{datetime.now().timestamp()}"

    async def _resolve_customer_db(
        self, email: str | None, phone: str | None, name: str
    ) -> str:
        async with self._db_pool.acquire() as conn:
            # Try email lookup
            if email:
                row = await conn.fetchrow(
                    "SELECT id FROM customers WHERE email = $1", email
                )
                if row:
                    return str(row["id"])

            # Try phone lookup
            if phone:
                row = await conn.fetchrow(
                    "SELECT id FROM customers WHERE phone = $1", phone
                )
                if row:
                    return str(row["id"])

            # Create new customer
            customer_id = await conn.fetchval(
                "INSERT INTO customers (email, phone, name) VALUES ($1, $2, $3) RETURNING id",
                email, phone, name,
            )
            return str(customer_id)

    # ── Ticket management ─────────────────────────────────────────────────────

    async def get_or_create_ticket(
        self, customer_id: str, channel: str, message: dict
    ) -> str:
        """Get active ticket or create new one."""
        if self._db_pool:
            return await self._get_or_create_ticket_db(customer_id, channel, message)

        # Mock
        import uuid
        return str(uuid.uuid4())[:8].upper()

    async def _get_or_create_ticket_db(
        self, customer_id: str, channel: str, message: dict
    ) -> str:
        async with self._db_pool.acquire() as conn:
            # For email: match by thread_id
            if channel == "email":
                channel_msg_id = message.get("channel_message_id", "")
                thread_id = channel_msg_id.split(":")[0] if ":" in channel_msg_id else ""
                if thread_id:
                    row = await conn.fetchrow(
                        """
                        SELECT t.id FROM tickets t
                        JOIN messages m ON m.ticket_id = t.id
                        WHERE t.customer_id = $1
                          AND t.status NOT IN ('resolved', 'closed')
                          AND m.channel_message_id LIKE $2
                        ORDER BY t.created_at DESC LIMIT 1
                        """,
                        int(customer_id), f"{thread_id}:%",
                    )
                    if row:
                        return str(row["id"])

            # For WhatsApp: reuse most recent open ticket
            elif channel == "whatsapp":
                row = await conn.fetchrow(
                    """
                    SELECT id FROM tickets
                    WHERE customer_id = $1
                      AND origin_channel = 'whatsapp'
                      AND status NOT IN ('resolved', 'closed', 'escalated')
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    int(customer_id),
                )
                if row:
                    return str(row["id"])

            # Create new ticket
            import random
            display_id = f"TKT-{random.randint(10000, 99999)}"
            ticket_id = await conn.fetchval(
                """
                INSERT INTO tickets
                  (customer_id, display_id, origin_channel, status, urgency, summary)
                VALUES ($1, $2, $3, 'open', 'medium', $4)
                RETURNING id
                """,
                int(customer_id),
                display_id,
                channel,
                message.get("subject") or message.get("body", "")[:100],
            )
            return str(ticket_id)

    # ── Message storage ───────────────────────────────────────────────────────

    async def store_message(
        self,
        ticket_id: str,
        channel: str,
        direction: str,
        content: str,
        channel_message_id: str | None = None,
    ) -> None:
        """Store a message in the database."""
        if not self._db_pool:
            logger.debug(f"[mock] store_message: {direction} via {channel} ({len(content)} chars)")
            return

        is_from_customer = direction == "inbound"
        is_ai = not is_from_customer

        async with self._db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages
                  (ticket_id, is_from_customer, is_ai_generated, channel, body, channel_message_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                int(ticket_id),
                is_from_customer,
                is_ai,
                channel,
                content,
                channel_message_id,
            )

    # ── History loading ───────────────────────────────────────────────────────

    async def load_history(self, ticket_id: str) -> list[dict]:
        """Load recent conversation history for a ticket."""
        if not self._db_pool:
            return []

        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT is_from_customer, body, channel, created_at
                FROM messages
                WHERE ticket_id = $1
                ORDER BY created_at ASC
                LIMIT 20
                """,
                int(ticket_id),
            )
            return [
                {
                    "role": "user" if r["is_from_customer"] else "assistant",
                    "content": r["body"],
                    "channel": r["channel"],
                }
                for r in rows
            ]

    # ── Agent execution ───────────────────────────────────────────────────────

    async def run_agent(
        self,
        message: dict,
        customer_id: str,
        ticket_id: str,
        channel: str,
        history: list[dict],
    ) -> dict[str, Any]:
        """
        Run the FTE agent on the message.

        Tries OpenAI Agents SDK first, falls back to Anthropic Claude.
        """
        # Build conversation input
        customer_message = message.get("body") or message.get("content", "")

        # Try OpenAI Agents SDK
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                return await self._run_openai_agent(
                    customer_message, customer_id, ticket_id, channel, history
                )
            except Exception as exc:
                logger.warning(f"OpenAI agent failed: {exc} — falling back to Anthropic")

        # Fall back to Anthropic (existing implementation)
        try:
            return await self._run_anthropic_agent(
                customer_message, customer_id, ticket_id, channel, history
            )
        except Exception as exc:
            logger.error(f"Anthropic agent also failed: {exc}")
            return {
                "response_text": (
                    "I apologize, I'm having trouble processing your request right now. "
                    "A human agent will follow up shortly."
                ),
                "escalated": True,
                "error": str(exc),
            }

    async def _run_openai_agent(
        self,
        message: str,
        customer_id: str,
        ticket_id: str,
        channel: str,
        history: list[dict],
    ) -> dict[str, Any]:
        """Run via OpenAI Agents SDK."""
        from agents import Runner
        from agent.customer_success_agent import customer_success_agent

        input_messages = []
        for h in history[-10:]:  # Last 10 messages for context
            input_messages.append({"role": h["role"], "content": h["content"]})

        input_messages.append({"role": "user", "content": message})

        result = await Runner.run(
            customer_success_agent,
            input=input_messages,
            context={
                "customer_id": customer_id,
                "ticket_id": ticket_id,
                "channel": channel,
            },
        )

        return {
            "response_text": result.final_output,
            "escalated": False,
            "tool_calls": len(result.new_items),
        }

    async def _run_anthropic_agent(
        self,
        message: str,
        customer_id: str,
        ticket_id: str,
        channel: str,
        history: list[dict],
    ) -> dict[str, Any]:
        """Run via existing Anthropic agent core."""
        from src.ingestion.normalizer import NormalizedMessage
        from src.agent.core import process_inbound_message
        from src.db.connection import get_db

        # Build a minimal NormalizedMessage for the existing pipeline
        normalized = NormalizedMessage(
            channel=channel,
            channel_message_id=f"worker-{datetime.now().timestamp()}",
            customer_email=None,
            customer_phone=None,
            customer_name=None,
            body=message,
            subject=None,
            raw_payload={},
        )

        async with get_db() as db:
            result = await process_inbound_message(normalized, db)

        if result:
            return {
                "response_text": result.response_text,
                "escalated": result.is_escalated,
            }
        return {"response_text": None, "escalated": False}

    # ── Response delivery ─────────────────────────────────────────────────────

    async def deliver_response(
        self, channel: str, original_message: dict, agent_result: dict
    ) -> None:
        """Deliver the agent response via the appropriate channel."""
        response_text = agent_result.get("response_text", "")

        if channel == "email":
            await self._deliver_email(original_message, response_text)
        elif channel == "whatsapp":
            await self._deliver_whatsapp(original_message, response_text)
        # web_form: response is returned synchronously in the API

    async def _deliver_email(self, message: dict, response: str) -> None:
        try:
            from src.channels.gmail import send_gmail_reply
            await send_gmail_reply(
                to_email=message.get("customer_email", ""),
                subject=message.get("subject", "Re: Your Support Request"),
                body=response,
                thread_id=message.get("gmail_thread_id"),
            )
        except Exception as exc:
            logger.error(f"Email delivery failed: {exc}")

    async def _deliver_whatsapp(self, message: dict, response: str) -> None:
        try:
            from src.channels.whatsapp import send_whatsapp_message
            phone = message.get("customer_phone", "")
            if phone:
                await send_whatsapp_message(phone, response)
        except Exception as exc:
            logger.error(f"WhatsApp delivery failed: {exc}")

    # ── Error handling ────────────────────────────────────────────────────────

    async def _handle_error(self, message: dict, error: Exception) -> None:
        """Send apologetic response and publish to DLQ."""
        apology = (
            "I apologize for the inconvenience. I'm having trouble processing "
            "your request right now. A human agent will follow up shortly."
        )
        channel = message.get("channel", "")

        try:
            if channel == "email" and message.get("customer_email"):
                await self._deliver_email(message, apology)
            elif channel == "whatsapp" and message.get("customer_phone"):
                await self._deliver_whatsapp(message, apology)
        except Exception as delivery_exc:
            logger.error(f"Error delivery also failed: {delivery_exc}")

        # Send to DLQ for human review
        await self.producer.send_to_dlq(
            original_topic=TOPICS["tickets_incoming"],
            original_payload=message,
            error=str(error),
        )

        # Publish error metric
        await self.producer.publish_metric(
            "message.processing_error",
            1.0,
            tags={"channel": channel, "error_type": type(error).__name__},
        )


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    processor = UnifiedMessageProcessor()
    try:
        await processor.start()
    except KeyboardInterrupt:
        logger.info("Shutting down message processor...")
    finally:
        await processor.producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
