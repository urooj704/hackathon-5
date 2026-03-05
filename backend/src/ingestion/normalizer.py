"""
Message Normalizer — converts channel-specific raw payloads into a unified
NormalizedMessage object that the rest of the system works with.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from src.db.models import ChannelEnum


@dataclass
class AttachmentMeta:
    filename: str
    mime_type: str
    size_bytes: Optional[int] = None
    url: Optional[str] = None  # temporary download URL if applicable


@dataclass
class NormalizedMessage:
    """
    Unified message format regardless of origin channel.
    This is what the identity resolver and agent always receive.
    """
    channel: ChannelEnum
    body: str
    timestamp: datetime

    # Customer identifiers — at least one present
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None

    # Channel-specific threading identifiers
    channel_message_id: Optional[str] = None
    channel_thread_id: Optional[str] = None  # Gmail thread ID, WA conversation ID

    # Attachments (metadata only — no binary content)
    attachments: List[AttachmentMeta] = field(default_factory=list)

    # Raw metadata (anything channel-specific we want to preserve)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0

    @property
    def primary_identifier(self) -> Optional[str]:
        """Returns email if available, otherwise phone."""
        return self.customer_email or self.customer_phone


# ─── Gmail Normalizer ─────────────────────────────────────────────────────────

def normalize_gmail(payload: Dict[str, Any]) -> NormalizedMessage:
    """
    Parse a Gmail message payload (from Gmail API .get() response) into NormalizedMessage.

    Expected payload structure:
    {
      "id": "18abc123",
      "threadId": "18abc000",
      "payload": {
        "headers": [...],  # From, Subject, Date, etc.
        "parts": [...],    # MIME parts
        "body": {...}
      }
    }
    """
    headers = {
        h["name"].lower(): h["value"]
        for h in payload.get("payload", {}).get("headers", [])
    }

    # Extract body text
    body = _extract_gmail_body(payload)

    # Parse sender
    from_header = headers.get("from", "")
    sender_email, sender_name = _parse_email_address(from_header)

    # Parse date
    date_str = headers.get("date", "")
    try:
        from email.utils import parsedate_to_datetime
        timestamp = parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        timestamp = datetime.now(timezone.utc)

    # Detect attachments
    attachments = _extract_gmail_attachments(payload)

    return NormalizedMessage(
        channel=ChannelEnum.EMAIL,
        body=body.strip(),
        timestamp=timestamp,
        customer_email=sender_email,
        customer_name=sender_name,
        channel_message_id=payload.get("id"),
        channel_thread_id=payload.get("threadId"),
        attachments=attachments,
        raw_metadata={
            "subject": headers.get("subject", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
        },
    )


def _extract_gmail_body(payload: Dict[str, Any]) -> str:
    """Recursively extract plain text body from Gmail MIME payload."""
    import base64

    msg_payload = payload.get("payload", {})

    # Single part message
    if msg_payload.get("mimeType") == "text/plain":
        data = msg_payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    # Multi-part — recurse
    parts = msg_payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        # Nested multipart
        if "parts" in part:
            sub_result = _extract_gmail_body({"payload": part})
            if sub_result:
                return sub_result

    return ""


def _extract_gmail_attachments(payload: Dict[str, Any]) -> List[AttachmentMeta]:
    attachments = []
    parts = payload.get("payload", {}).get("parts", [])
    for part in parts:
        filename = part.get("filename", "")
        if filename:
            attachments.append(
                AttachmentMeta(
                    filename=filename,
                    mime_type=part.get("mimeType", "application/octet-stream"),
                    size_bytes=part.get("body", {}).get("size"),
                )
            )
    return attachments


def _parse_email_address(raw: str):
    """Parse 'Name <email@example.com>' → (email, name)."""
    import re
    match = re.match(r"^(.+?)\s*<(.+?)>$", raw.strip())
    if match:
        return match.group(2).strip().lower(), match.group(1).strip().strip('"')
    # No name, just email
    email = raw.strip().lower()
    return (email if "@" in email else None), None


# ─── WhatsApp Normalizer ──────────────────────────────────────────────────────

def normalize_whatsapp(payload: Dict[str, Any]) -> Optional[NormalizedMessage]:
    """
    Parse a WhatsApp Cloud API webhook payload into NormalizedMessage.

    Meta sends nested structure:
    {
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{"id": ..., "from": "15551234567", "text": {"body": "..."}, "timestamp": ...}],
            "contacts": [{"profile": {"name": "..."}, "wa_id": "..."}]
          }
        }]
      }]
    }
    """
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]

        messages = value.get("messages", [])
        if not messages:
            return None  # Not a message event (could be status update)

        msg = messages[0]

        # Only handle text messages for now
        if msg.get("type") != "text":
            # Could be image, audio, etc. — acknowledge but don't process
            body = f"[{msg.get('type', 'unknown').upper()} message received]"
        else:
            body = msg["text"]["body"]

        phone = msg["from"]  # Always E.164 format from Meta
        timestamp = datetime.fromtimestamp(int(msg["timestamp"]), tz=timezone.utc)

        # Get display name from contacts array
        contacts = value.get("contacts", [])
        name = None
        if contacts:
            name = contacts[0].get("profile", {}).get("name")

        return NormalizedMessage(
            channel=ChannelEnum.WHATSAPP,
            body=body.strip(),
            timestamp=timestamp,
            customer_phone=f"+{phone}" if not phone.startswith("+") else phone,
            customer_name=name,
            channel_message_id=msg["id"],
            channel_thread_id=phone,  # WA thread = phone number
            raw_metadata={
                "wa_id": phone,
                "message_type": msg.get("type"),
                "phone_number_id": value.get("metadata", {}).get("phone_number_id"),
            },
        )
    except (KeyError, IndexError, TypeError):
        return None


# ─── Web Form Normalizer ──────────────────────────────────────────────────────

def normalize_web_form(payload: Dict[str, Any]) -> NormalizedMessage:
    """
    Parse a web support form submission into NormalizedMessage.

    Expected payload (from our FastAPI endpoint):
    {
      "email": "user@example.com",
      "name": "Jane Doe",
      "subject": "Can't connect Airtable",
      "category": "technical",
      "message": "I've been trying to connect...",
      "form_submission_id": "sub_abc123"
    }
    """
    email = payload.get("email", "").strip().lower() or None
    name = payload.get("name", "").strip() or None
    subject = payload.get("subject", "").strip()
    message_body = payload.get("message", "").strip()

    # Prepend subject to body for context
    if subject:
        full_body = f"[Subject: {subject}]\n\n{message_body}"
    else:
        full_body = message_body

    return NormalizedMessage(
        channel=ChannelEnum.WEB_FORM,
        body=full_body,
        timestamp=datetime.now(timezone.utc),
        customer_email=email,
        customer_name=name,
        channel_message_id=payload.get("form_submission_id"),
        raw_metadata={
            "subject": subject,
            "category": payload.get("category", "general"),
        },
    )
