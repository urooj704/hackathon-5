"""
Kafka Client — FlowForge Customer Success FTE

Provides async producer and consumer wrappers for the multi-channel
event streaming pipeline.

Topics:
  fte.tickets.incoming          — unified inbound from all channels
  fte.channels.email.inbound    — Gmail-specific inbound
  fte.channels.whatsapp.inbound — WhatsApp-specific inbound
  fte.channels.webform.inbound  — Web form submissions
  fte.channels.email.outbound   — Email replies to send
  fte.channels.whatsapp.outbound— WhatsApp replies to send
  fte.escalations               — Escalation events for human agents
  fte.metrics                   — Performance and operational metrics
  fte.dlq                       — Dead letter queue for failed messages
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Coroutine

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
)

# ─── Topic Registry ───────────────────────────────────────────────────────────

TOPICS = {
    # Unified inbound (all channels merge here)
    "tickets_incoming":    "fte.tickets.incoming",

    # Channel-specific inbound
    "email_inbound":       "fte.channels.email.inbound",
    "whatsapp_inbound":    "fte.channels.whatsapp.inbound",
    "webform_inbound":     "fte.channels.webform.inbound",

    # Channel-specific outbound
    "email_outbound":      "fte.channels.email.outbound",
    "whatsapp_outbound":   "fte.channels.whatsapp.outbound",

    # Escalations (human agents subscribe)
    "escalations":         "fte.escalations",

    # Metrics and monitoring
    "metrics":             "fte.metrics",

    # Dead letter queue for failed processing
    "dlq":                 "fte.dlq",
}

# Reverse map for topic name → key lookups
TOPIC_NAMES = {v: k for k, v in TOPICS.items()}


# ─── Event envelope ───────────────────────────────────────────────────────────

def build_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap a payload in a standard event envelope."""
    return {
        "event_type": event_type,
        "schema_version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "customer-success-fte",
        **payload,
    }


# ─── Producer ─────────────────────────────────────────────────────────────────

class FTEKafkaProducer:
    """
    Async Kafka producer for the FTE pipeline.

    Usage:
        producer = FTEKafkaProducer()
        await producer.start()
        await producer.publish(TOPICS["tickets_incoming"], {...})
        await producer.stop()
    """

    def __init__(self, bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS):
        self.bootstrap_servers = bootstrap_servers
        self._producer = None

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",           # Wait for all replicas to confirm
                enable_idempotence=True,
                compression_type="gzip",
            )
            await self._producer.start()
            logger.info("Kafka producer started", extra={"servers": self.bootstrap_servers})

        except ImportError:
            logger.warning("aiokafka not installed — using mock producer")
            self._producer = _MockProducer()
        except Exception as exc:
            logger.error(f"Kafka producer start failed: {exc} — using mock producer")
            self._producer = _MockProducer()

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
        event_type: str | None = None,
    ) -> None:
        """
        Publish an event to a Kafka topic.

        Args:
            topic:      Kafka topic name (use TOPICS["key"])
            payload:    Event data dict
            key:        Optional partition key (e.g., customer_id for ordering)
            event_type: Optional event type for envelope (auto-derived from topic if None)
        """
        if not self._producer:
            raise RuntimeError("Producer not started. Call await producer.start() first.")

        event_type = event_type or TOPIC_NAMES.get(topic, topic)
        envelope = build_event(event_type, payload)

        await self._producer.send_and_wait(topic, envelope, key=key)
        logger.debug(f"Published to {topic}", extra={"key": key, "event_type": event_type})

    async def publish_incoming_ticket(self, normalized_message: dict) -> None:
        """Convenience: publish a normalized inbound message."""
        channel = normalized_message.get("channel", "unknown")
        customer_id = normalized_message.get("customer_email") or normalized_message.get("customer_phone")

        await self.publish(
            topic=TOPICS["tickets_incoming"],
            payload=normalized_message,
            key=customer_id,
            event_type=f"ticket.incoming.{channel}",
        )

    async def publish_escalation(
        self,
        ticket_id: str,
        tier: str,
        reason: str,
        route_to: str,
        channel: str,
    ) -> None:
        """Convenience: publish an escalation event."""
        await self.publish(
            topic=TOPICS["escalations"],
            payload={
                "ticket_id": ticket_id,
                "tier": tier,
                "reason": reason,
                "route_to": route_to,
                "channel": channel,
                "requires_human": True,
            },
            key=ticket_id,
            event_type="escalation.created",
        )

    async def publish_metric(
        self,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Convenience: publish a metric event."""
        await self.publish(
            topic=TOPICS["metrics"],
            payload={
                "metric": metric_name,
                "value": value,
                "tags": tags or {},
            },
            event_type="metric.recorded",
        )

    async def send_to_dlq(
        self,
        original_topic: str,
        original_payload: dict,
        error: str,
    ) -> None:
        """Send a failed message to the Dead Letter Queue."""
        await self.publish(
            topic=TOPICS["dlq"],
            payload={
                "original_topic": original_topic,
                "original_payload": original_payload,
                "error": error,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "requires_manual_review": True,
            },
            event_type="message.dead_lettered",
        )


# ─── Consumer ─────────────────────────────────────────────────────────────────

class FTEKafkaConsumer:
    """
    Async Kafka consumer for the FTE pipeline.

    Usage:
        consumer = FTEKafkaConsumer(
            topics=[TOPICS["tickets_incoming"]],
            group_id="fte-message-processor",
        )
        await consumer.start()
        await consumer.consume(handler_func)
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str,
        bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset: str = "earliest",
    ):
        self.topics = topics
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers
        self.auto_offset_reset = auto_offset_reset
        self._consumer = None

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaConsumer

            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=False,  # Manual commit for exactly-once semantics
                max_poll_records=10,
            )
            await self._consumer.start()
            logger.info(
                "Kafka consumer started",
                extra={"topics": self.topics, "group": self.group_id},
            )

        except ImportError:
            logger.warning("aiokafka not installed — using mock consumer")
            self._consumer = _MockConsumer()
        except Exception as exc:
            logger.error(f"Kafka consumer start failed: {exc}")
            self._consumer = _MockConsumer()

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")

    async def consume(
        self,
        handler: Callable[[str, dict], Coroutine],
        producer: FTEKafkaProducer | None = None,
    ) -> None:
        """
        Consume messages in a loop, calling handler for each.

        Args:
            handler: Async function(topic, message_dict) -> None
            producer: Optional producer for DLQ publishing on errors
        """
        async for msg in self._consumer:
            try:
                await handler(msg.topic, msg.value)
                await self._consumer.commit()
            except Exception as exc:
                logger.error(
                    f"Error processing message from {msg.topic}: {exc}",
                    exc_info=True,
                )
                if producer:
                    await producer.send_to_dlq(
                        original_topic=msg.topic,
                        original_payload=msg.value,
                        error=str(exc),
                    )

    async def __aiter__(self) -> AsyncIterator[tuple[str, dict]]:
        """Async iterator for manual message consumption."""
        async for msg in self._consumer:
            yield msg.topic, msg.value
            await self._consumer.commit()


# ─── Mock implementations (for development without Kafka) ─────────────────────

class _MockProducer:
    """Logs events instead of sending to Kafka (for local dev/testing)."""

    async def start(self):
        logger.info("[MockProducer] Started (no Kafka connection)")

    async def stop(self):
        logger.info("[MockProducer] Stopped")

    async def send_and_wait(self, topic: str, value: Any, key: str | None = None):
        logger.info(f"[MockProducer] → {topic} key={key}: {json.dumps(value, default=str)[:200]}")


class _MockConsumer:
    """Returns no messages (for local dev/testing)."""

    async def start(self):
        logger.info("[MockConsumer] Started (no Kafka connection — no messages will be consumed)")

    async def stop(self):
        logger.info("[MockConsumer] Stopped")

    async def commit(self):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration
