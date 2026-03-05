"""
Redis-based job queue for deferred / retry processing.

Used primarily for:
  - Gmail polling jobs triggered by cron / Pub/Sub
  - Retrying failed message processing

Queue structure:
  - Jobs are pushed as JSON onto a Redis list key: "flowforge:jobs:{queue_name}"
  - Workers BLPOP from the list (blocking, left-pop)
  - Failed jobs are pushed to "flowforge:jobs:{queue_name}:dead" after max retries

Usage:
  # Enqueue a job
  await enqueue("gmail_poll", {"history_id": "12345"})

  # Run the worker (blocking, run in separate process)
  asyncio.run(run_worker("gmail_poll"))
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional

import redis.asyncio as aioredis
import structlog

from src.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

# Queue key prefixes
_QUEUE_PREFIX = "flowforge:jobs"
_DEAD_SUFFIX = ":dead"
MAX_RETRIES = 3


# ─── Job schema ───────────────────────────────────────────────────────────────

def _make_job(queue: str, payload: Dict[str, Any], retries: int = 0) -> str:
    return json.dumps(
        {
            "job_id": str(uuid.uuid4()),
            "queue": queue,
            "payload": payload,
            "retries": retries,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


# ─── Enqueue ──────────────────────────────────────────────────────────────────

async def enqueue(queue: str, payload: Dict[str, Any]) -> None:
    """Push a job onto the named Redis queue."""
    async with aioredis.from_url(settings.redis_url, decode_responses=True) as redis:
        key = f"{_QUEUE_PREFIX}:{queue}"
        job_str = _make_job(queue, payload)
        await redis.rpush(key, job_str)
        log.info("job_enqueued", queue=queue, payload_keys=list(payload.keys()))


# ─── Worker ───────────────────────────────────────────────────────────────────

HandlerFn = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]

# Registry: queue_name → async handler function
_HANDLERS: Dict[str, HandlerFn] = {}


def register_handler(queue: str, fn: HandlerFn) -> None:
    """Register a coroutine function as the handler for a queue."""
    _HANDLERS[queue] = fn
    log.info("worker_handler_registered", queue=queue)


async def run_worker(queue: str, timeout: float = 5.0) -> None:
    """
    Blocking worker loop for a single queue.
    Run this in a dedicated process / container.

    Args:
        queue: Queue name to consume from
        timeout: BLPOP timeout in seconds (0 = block forever)
    """
    handler = _HANDLERS.get(queue)
    if handler is None:
        raise ValueError(f"No handler registered for queue '{queue}'")

    queue_key = f"{_QUEUE_PREFIX}:{queue}"
    dead_key = f"{queue_key}{_DEAD_SUFFIX}"

    log.info("worker_started", queue=queue)

    async with aioredis.from_url(settings.redis_url, decode_responses=True) as redis:
        while True:
            try:
                result = await redis.blpop(queue_key, timeout=timeout)
                if result is None:
                    # Timeout — loop again
                    continue

                _, job_str = result
                job = json.loads(job_str)
                job_id = job.get("job_id", "?")
                payload = job.get("payload", {})
                retries = job.get("retries", 0)

                log.info("job_processing", job_id=job_id, queue=queue, retries=retries)

                try:
                    await handler(payload)
                    log.info("job_completed", job_id=job_id)
                except Exception as exc:
                    log.error("job_failed", job_id=job_id, error=str(exc), retries=retries)
                    if retries < MAX_RETRIES:
                        # Re-enqueue with incremented retry count
                        retry_job = _make_job(queue, payload, retries + 1)
                        await redis.rpush(queue_key, retry_job)
                        log.info("job_requeued", job_id=job_id, next_retry=retries + 1)
                    else:
                        # Move to dead letter queue
                        await redis.rpush(dead_key, job_str)
                        log.warning("job_dead_lettered", job_id=job_id)

            except asyncio.CancelledError:
                log.info("worker_stopping", queue=queue)
                break
            except Exception as exc:
                log.error("worker_loop_error", queue=queue, error=str(exc))
                await asyncio.sleep(1)


# ─── Register Gmail poll handler ──────────────────────────────────────────────

async def _gmail_poll_handler(payload: Dict[str, Any]) -> None:
    """Handler for gmail_poll jobs."""
    from src.channels.gmail import _poll_and_process

    history_id = payload.get("history_id")
    await _poll_and_process(history_id=history_id)


register_handler("gmail_poll", _gmail_poll_handler)


# ─── Entrypoint for standalone worker process ─────────────────────────────────

if __name__ == "__main__":
    import sys

    queue_name = sys.argv[1] if len(sys.argv) > 1 else "gmail_poll"
    asyncio.run(run_worker(queue_name))
