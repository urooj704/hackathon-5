"""
Tests for channel HTTP endpoints (WhatsApp webhook, Web Form).
Uses FastAPI TestClient with mocked DB and agent pipeline.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Create a TestClient without running startup events (no real DB needed)."""
    from src.app import app
    # Disable lifespan for unit tests
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ─── WhatsApp webhook verification ──────────────────────────────────────────

class TestWhatsAppWebhookVerification:
    def test_valid_verify_token(self, client):
        resp = client.get(
            "/channels/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "flowforge_verify",
                "hub.challenge": "CHALLENGE_TOKEN",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "CHALLENGE_TOKEN"

    def test_invalid_verify_token(self, client):
        resp = client.get(
            "/channels/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "CHALLENGE_TOKEN",
            },
        )
        assert resp.status_code == 403

    def test_wrong_mode(self, client):
        resp = client.get(
            "/channels/whatsapp/webhook",
            params={
                "hub.mode": "unsubscribe",
                "hub.verify_token": "flowforge_verify",
                "hub.challenge": "X",
            },
        )
        assert resp.status_code == 403


# ─── WhatsApp incoming message ────────────────────────────────────────────────

class TestWhatsAppIncomingMessage:
    def _make_whatsapp_payload(self, text="Hello"):
        return {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.test001",
                                        "from": "15551234567",
                                        "type": "text",
                                        "text": {"body": text},
                                        "timestamp": "1740000000",
                                    }
                                ],
                                "contacts": [
                                    {"profile": {"name": "Test User"}, "wa_id": "15551234567"}
                                ],
                                "metadata": {"phone_number_id": "999"},
                            }
                        }
                    ]
                }
            ]
        }

    def test_webhook_returns_200_immediately(self, client):
        """WhatsApp webhook must always return 200 quickly."""
        with patch(
            "src.channels.whatsapp._process_whatsapp_payload", new_callable=AsyncMock
        ):
            resp = client.post(
                "/channels/whatsapp/webhook",
                json=self._make_whatsapp_payload(),
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_empty_body_still_returns_200(self, client):
        """Malformed payloads must not cause 4xx/5xx (Meta would retry forever)."""
        resp = client.post(
            "/channels/whatsapp/webhook",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200


# ─── Web Form endpoint ────────────────────────────────────────────────────────

class TestWebFormEndpoint:
    def _mock_pipeline_result(self):
        from src.agent.core import AgentResult
        from unittest.mock import MagicMock

        ticket = MagicMock()
        ticket.display_id = "TKT-00001"
        return AgentResult(
            response_text="Hi there,\n\nHere's how to fix your automation...\n\nHow else can I help?",
            ticket=ticket,
            was_escalated=False,
        )

    def test_valid_submission_returns_response(self, client):
        with patch(
            "src.channels.web_form.process_inbound_message",
            new_callable=AsyncMock,
            return_value=self._mock_pipeline_result(),
        ), patch(
            "src.channels.web_form.get_db",
        ) as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/channels/web-form/submit",
                json={
                    "email": "user@example.com",
                    "name": "Test User",
                    "subject": "Automation not working",
                    "category": "technical",
                    "message": "My HubSpot trigger keeps failing.",
                    "form_submission_id": "sub_abc",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["ticket_id"] == "TKT-00001"
        assert "automation" in data["message"].lower() or "help" in data["message"].lower()

    def test_missing_email_returns_422(self, client):
        resp = client.post(
            "/channels/web-form/submit",
            json={
                "name": "No Email",
                "message": "Hello",
            },
        )
        assert resp.status_code == 422

    def test_message_too_short_returns_422(self, client):
        resp = client.post(
            "/channels/web-form/submit",
            json={
                "email": "user@example.com",
                "message": "Hi",  # < 5 chars
            },
        )
        assert resp.status_code == 422

    def test_duplicate_returns_duplicate_status(self, client):
        with patch(
            "src.channels.web_form.process_inbound_message",
            new_callable=AsyncMock,
            return_value=None,  # None = duplicate
        ), patch(
            "src.channels.web_form.get_db",
        ) as mock_get_db:
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = client.post(
                "/channels/web-form/submit",
                json={
                    "email": "user@example.com",
                    "message": "Duplicate submission",
                    "form_submission_id": "sub_dup",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"


# ─── Health checks ────────────────────────────────────────────────────────────

class TestHealthEndpoints:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
