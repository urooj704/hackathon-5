"""
Tests for message normalization and customer identity resolution.
"""

import pytest
from datetime import timezone

from src.ingestion.normalizer import (
    normalize_gmail,
    normalize_whatsapp,
    normalize_web_form,
    NormalizedMessage,
)
from src.db.models import ChannelEnum


# ─── normalize_gmail ─────────────────────────────────────────────────────────

class TestNormalizeGmail:
    def _make_payload(self, from_header="Jane Doe <jane@example.com>", body_text="Hello"):
        import base64
        encoded = base64.urlsafe_b64encode(body_text.encode()).decode()
        return {
            "id": "msg_001",
            "threadId": "thread_001",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": from_header},
                    {"name": "Date", "value": "Mon, 24 Feb 2026 10:00:00 +0000"},
                    {"name": "Subject", "value": "Help with automation"},
                ],
                "body": {"data": encoded},
            },
        }

    def test_extracts_email_and_name(self):
        msg = normalize_gmail(self._make_payload())
        assert msg.customer_email == "jane@example.com"
        assert msg.customer_name == "Jane Doe"

    def test_extracts_body(self):
        msg = normalize_gmail(self._make_payload(body_text="My trigger is broken"))
        assert "trigger" in msg.body

    def test_channel_is_email(self):
        msg = normalize_gmail(self._make_payload())
        assert msg.channel == ChannelEnum.EMAIL

    def test_message_id_set(self):
        msg = normalize_gmail(self._make_payload())
        assert msg.channel_message_id == "msg_001"

    def test_thread_id_set(self):
        msg = normalize_gmail(self._make_payload())
        assert msg.channel_thread_id == "thread_001"

    def test_no_name_in_from(self):
        msg = normalize_gmail(self._make_payload(from_header="plain@example.com"))
        assert msg.customer_email == "plain@example.com"
        assert msg.customer_name is None


# ─── normalize_whatsapp ───────────────────────────────────────────────────────

class TestNormalizeWhatsapp:
    def _make_payload(self, phone="15551234567", text="Hey, need help"):
        return {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.001",
                                        "from": phone,
                                        "type": "text",
                                        "text": {"body": text},
                                        "timestamp": "1740000000",
                                    }
                                ],
                                "contacts": [
                                    {"profile": {"name": "Alex"}, "wa_id": phone}
                                ],
                                "metadata": {"phone_number_id": "999"},
                            }
                        }
                    ]
                }
            ]
        }

    def test_extracts_phone(self):
        msg = normalize_whatsapp(self._make_payload())
        assert msg.customer_phone == "+15551234567"

    def test_extracts_body(self):
        msg = normalize_whatsapp(self._make_payload(text="pls help 😊"))
        assert "pls help" in msg.body

    def test_channel_is_whatsapp(self):
        msg = normalize_whatsapp(self._make_payload())
        assert msg.channel == ChannelEnum.WHATSAPP

    def test_extracts_name(self):
        msg = normalize_whatsapp(self._make_payload())
        assert msg.customer_name == "Alex"

    def test_no_messages_returns_none(self):
        payload = {"entry": [{"changes": [{"value": {"messages": []}}]}]}
        result = normalize_whatsapp(payload)
        assert result is None

    def test_bad_payload_returns_none(self):
        assert normalize_whatsapp({}) is None


# ─── normalize_web_form ───────────────────────────────────────────────────────

class TestNormalizeWebForm:
    def test_prepends_subject(self):
        msg = normalize_web_form(
            {
                "email": "user@test.com",
                "subject": "Billing Question",
                "message": "I was charged twice.",
                "form_submission_id": "sub_001",
            }
        )
        assert "[Subject: Billing Question]" in msg.body
        assert "charged twice" in msg.body

    def test_channel_is_web_form(self):
        msg = normalize_web_form({"email": "a@b.com", "message": "Hello"})
        assert msg.channel == ChannelEnum.WEB_FORM

    def test_email_extracted(self):
        msg = normalize_web_form({"email": "USER@EXAMPLE.COM", "message": "Hi"})
        assert msg.customer_email == "user@example.com"

    def test_no_subject_no_prefix(self):
        msg = normalize_web_form({"email": "a@b.com", "message": "Just a message"})
        assert msg.body == "Just a message"


# ─── identity resolver ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestResolveCustomer:
    async def test_creates_new_customer_by_email(self, db):
        from src.ingestion.identity import resolve_customer
        from src.ingestion.normalizer import NormalizedMessage, ChannelEnum
        from datetime import datetime, timezone

        msg = NormalizedMessage(
            channel=ChannelEnum.EMAIL,
            body="Test",
            timestamp=datetime.now(timezone.utc),
            customer_email="new@example.com",
            customer_name="New User",
        )
        customer = await resolve_customer(db, msg)
        assert customer.id is not None
        assert customer.email == "new@example.com"
        assert customer.name == "New User"

    async def test_finds_existing_customer_by_email(self, db, sample_customer):
        from src.ingestion.identity import resolve_customer
        from src.ingestion.normalizer import NormalizedMessage, ChannelEnum
        from datetime import datetime, timezone

        msg = NormalizedMessage(
            channel=ChannelEnum.EMAIL,
            body="Follow up",
            timestamp=datetime.now(timezone.utc),
            customer_email="test@example.com",
        )
        customer = await resolve_customer(db, msg)
        assert customer.id == sample_customer.id

    async def test_enriches_phone_when_missing(self, db, sample_customer):
        from src.ingestion.identity import resolve_customer
        from src.ingestion.normalizer import NormalizedMessage, ChannelEnum
        from datetime import datetime, timezone

        msg = NormalizedMessage(
            channel=ChannelEnum.WHATSAPP,
            body="Hey",
            timestamp=datetime.now(timezone.utc),
            customer_email="test@example.com",
            customer_phone="+15559999999",
        )
        customer = await resolve_customer(db, msg)
        assert customer.phone == "+15559999999"
