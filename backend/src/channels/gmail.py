"""
Gmail channel handler.

Responsibilities:
  - OAuth2 callback endpoint (stores token to disk)
  - Google Pub/Sub push webhook endpoint (receives new-message notifications)
  - Admin poll endpoint (manual trigger for local dev / cron)
  - send_gmail_reply() — sends an email reply via Gmail API

Gmail message IDs are stored as "thread_id:message_id" in channel_message_id
so that the thread-matching logic in core.py can match by thread prefix.
"""

from __future__ import annotations

import base64
import email as email_lib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.core import process_inbound_message
from src.config import get_settings
from src.db.connection import get_db
from src.ingestion.normalizer import normalize_gmail

log = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/channels/gmail", tags=["gmail"])

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


# ─── Gmail API client factory ─────────────────────────────────────────────────

def _get_gmail_service():
    """Build an authenticated Gmail API service from stored token file."""
    import json
    from pathlib import Path

    token_path = Path(settings.gmail_credentials_file)
    if not token_path.exists():
        raise RuntimeError(
            f"Gmail token file not found: {token_path}. "
            "Complete OAuth at GET /channels/gmail/oauth/start"
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Refresh expired token
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ─── OAuth2 flow ──────────────────────────────────────────────────────────────

@router.get("/oauth/start")
async def gmail_oauth_start():
    """Redirect to Google OAuth consent screen."""
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "redirect_uris": [settings.gmail_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.gmail_redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return JSONResponse({"auth_url": auth_url})


@router.get("/oauth/callback")
async def gmail_oauth_callback(code: str, state: Optional[str] = None):
    """
    Handle the OAuth2 callback from Google.
    Exchanges code for tokens and saves them to disk.
    """
    from pathlib import Path

    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "redirect_uris": [settings.gmail_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.gmail_redirect_uri,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    Path(settings.gmail_credentials_file).write_text(creds.to_json())
    log.info("gmail_oauth_complete", token_file=settings.gmail_credentials_file)
    return {"status": "ok", "message": "Gmail connected successfully."}


# ─── Google Pub/Sub push webhook ──────────────────────────────────────────────

@router.post("/webhook")
async def gmail_pubsub_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Receives Google Cloud Pub/Sub push notifications.

    Google sends a JSON envelope:
    {
      "message": {
        "data": "<base64-encoded JSON with emailAddress and historyId>",
        "messageId": "...",
        "publishTime": "..."
      },
      "subscription": "..."
    }

    We acknowledge immediately (HTTP 200) and process in background.
    """
    try:
        body = await request.json()
        data_b64 = body.get("message", {}).get("data", "")
        if data_b64:
            import json
            decoded = json.loads(base64.b64decode(data_b64 + "==").decode("utf-8"))
            history_id = decoded.get("historyId")
            if history_id:
                background_tasks.add_task(_poll_and_process, history_id=history_id)
    except Exception as exc:
        log.warning("gmail_webhook_parse_error", error=str(exc))

    # Always return 200 to acknowledge Pub/Sub delivery
    return {"status": "ok"}


# ─── Admin poll endpoint (local dev / cron) ───────────────────────────────────

@router.post("/poll")
async def gmail_poll(background_tasks: BackgroundTasks):
    """Manually trigger Gmail inbox polling (useful for local dev)."""
    background_tasks.add_task(_poll_and_process)
    return {"status": "polling_started"}


# ─── Core polling logic ───────────────────────────────────────────────────────

async def _poll_and_process(history_id: Optional[str] = None) -> None:
    """
    Fetch unread INBOX messages from Gmail and run each through the agent pipeline.
    Called from both the Pub/Sub webhook and the admin poll endpoint.
    """
    try:
        service = _get_gmail_service()
    except RuntimeError as exc:
        log.error("gmail_service_unavailable", error=str(exc))
        return

    try:
        # List unread messages in INBOX
        result = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=20)
            .execute()
        )
        messages = result.get("messages", [])

        if not messages:
            log.info("gmail_poll_no_new_messages")
            return

        log.info("gmail_poll_found", count=len(messages))

        for msg_ref in messages:
            await _process_gmail_message(service, msg_ref["id"])

    except HttpError as exc:
        log.error("gmail_api_error", error=str(exc))


async def _process_gmail_message(service, message_id: str) -> None:
    """Fetch a single Gmail message, run the pipeline, and send reply."""
    try:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        thread_id = msg.get("threadId", message_id)

        # Normalize
        normalized = normalize_gmail(msg)
        # Store as "thread_id:message_id" for thread-matching
        normalized.channel_message_id = f"{thread_id}:{message_id}"
        normalized.channel_thread_id = thread_id

        # Run full pipeline
        async with get_db() as db:
            result = await process_inbound_message(normalized, db)

        if result is None:
            return  # Duplicate

        # Send reply
        if result.response_text and normalized.customer_email:
            await send_gmail_reply(
                service=service,
                thread_id=thread_id,
                to_email=normalized.customer_email,
                reply_body=result.response_text,
                original_message_id=message_id,
            )

        # Mark as read
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    except Exception as exc:
        log.error("gmail_message_processing_error", message_id=message_id, error=str(exc))


# ─── Send reply ───────────────────────────────────────────────────────────────

async def send_gmail_reply(
    service,
    thread_id: str,
    to_email: str,
    reply_body: str,
    original_message_id: Optional[str] = None,
) -> None:
    """
    Send an email reply via Gmail API, threaded correctly.
    Converts markdown-style bold (**text**) to HTML <b>text</b>.
    """
    # Build MIME message
    mime_msg = MIMEMultipart("alternative")
    mime_msg["To"] = to_email
    mime_msg["From"] = settings.support_email
    mime_msg["Subject"] = "Re: Your FlowForge Support Request"

    if original_message_id:
        mime_msg["In-Reply-To"] = original_message_id
        mime_msg["References"] = original_message_id

    # Plain text part
    mime_msg.attach(MIMEText(reply_body, "plain"))

    # HTML part — convert **bold** and `code` for basic formatting
    html_body = (
        reply_body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    import re
    html_body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html_body)
    html_body = re.sub(r"`(.+?)`", r"<code>\1</code>", html_body)
    mime_msg.attach(MIMEText(f"<html><body>{html_body}</body></html>", "html"))

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

    service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": thread_id},
    ).execute()

    log.info("gmail_reply_sent", to=to_email, thread_id=thread_id)
