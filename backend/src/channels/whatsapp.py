"""
WhatsApp channel handler (Meta Cloud API).

Endpoints:
  GET  /channels/whatsapp/webhook  — webhook verification challenge
  POST /channels/whatsapp/webhook  — incoming messages

Outbound messages use send_whatsapp_message() via httpx.
"""

from __future__ import annotations

import hashlib
import hmac

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from src.agent.core import process_inbound_message
from src.config import get_settings
from src.db.connection import get_db
from src.ingestion.normalizer import normalize_whatsapp

log = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/channels/whatsapp", tags=["whatsapp"])


# ─── Webhook verification (GET) ───────────────────────────────────────────────

@router.get("/webhook")
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """
    Meta sends a GET request with hub.challenge to verify the webhook URL.
    We must echo back hub.challenge if the verify token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        log.info("whatsapp_webhook_verified")
        return PlainTextResponse(hub_challenge)

    log.warning("whatsapp_webhook_verification_failed", token=hub_verify_token)
    raise HTTPException(status_code=403, detail="Verification failed")


# ─── Incoming message webhook (POST) ─────────────────────────────────────────

@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
):
    """
    Receives WhatsApp messages from Meta.
    Acknowledges immediately (HTTP 200) and processes in background.
    """
    raw_body = await request.body()

    # Verify HMAC signature if access token is configured
    if settings.whatsapp_access_token:
        _verify_whatsapp_signature(raw_body, x_hub_signature_256)

    try:
        payload = await request.json()
    except Exception:
        return {"status": "ok"}  # Always 200 to avoid Meta retries

    background_tasks.add_task(_process_whatsapp_payload, payload)
    return {"status": "ok"}


# ─── Processing logic ─────────────────────────────────────────────────────────

async def _process_whatsapp_payload(payload: dict) -> None:
    """Normalize, run agent pipeline, send reply."""
    normalized = normalize_whatsapp(payload)
    if normalized is None:
        # Status update or unsupported message type — ignore
        return

    if not normalized.body.strip():
        return

    log.info(
        "whatsapp_message_received",
        phone=normalized.customer_phone,
        length=len(normalized.body),
    )

    async with get_db() as db:
        result = await process_inbound_message(normalized, db)

    if result is None:
        return  # Duplicate

    if result.response_text and normalized.customer_phone:
        await send_whatsapp_message(normalized.customer_phone, result.response_text)


# ─── Send message ─────────────────────────────────────────────────────────────

async def send_whatsapp_message(to_phone: str, body: str) -> None:
    """
    Send a WhatsApp text message via Meta Cloud API.

    Args:
        to_phone: E.164 phone number (e.g. "+15551234567")
        body: Plain text message content
    """
    if not settings.whatsapp_phone_number_id or not settings.whatsapp_access_token:
        log.warning("whatsapp_send_skipped", reason="credentials_not_configured")
        return

    url = (
        f"{settings.whatsapp_api_url}"
        f"/{settings.whatsapp_phone_number_id}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    # WhatsApp requires E.164 without leading +
    phone_id = to_phone.lstrip("+")

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_id,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            log.info("whatsapp_message_sent", to=phone_id, status=resp.status_code)
    except httpx.HTTPStatusError as exc:
        log.error(
            "whatsapp_send_error",
            to=phone_id,
            status=exc.response.status_code,
            body=exc.response.text[:200],
        )
    except Exception as exc:
        log.error("whatsapp_send_error", to=phone_id, error=str(exc))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _verify_whatsapp_signature(raw_body: bytes, signature_header: str) -> None:
    """
    Verify the X-Hub-Signature-256 header from Meta.
    Raises HTTP 401 if the signature doesn't match.
    """
    if not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing signature")

    expected = hmac.new(  # noqa: S324
        settings.whatsapp_access_token.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    received = signature_header[len("sha256="):]

    if not hmac.compare_digest(expected, received):
        log.warning("whatsapp_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
