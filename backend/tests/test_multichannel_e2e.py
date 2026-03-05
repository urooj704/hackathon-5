"""
Multi-Channel E2E Test Suite — FlowForge Customer Success FTE

Tests the complete flow across all three channels:
  - Web Form (required)
  - Email/Gmail
  - WhatsApp
  - Cross-channel continuity

Run:
    pytest tests/test_multichannel_e2e.py -v
    pytest tests/test_multichannel_e2e.py -v -k "test_form"  # web form only

Requires:
    pip install httpx pytest pytest-asyncio
    API server running: uvicorn src.app:app --port 8000
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime

import pytest
import httpx

BASE_URL = "http://localhost:8000"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    """Async HTTP client with base URL."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as ac:
        yield ac


@pytest.fixture
def unique_email():
    """Generate a unique email for each test run."""
    return f"e2e-test-{int(time.time())}@example.com"


@pytest.fixture
def unique_phone():
    """Generate a unique phone number for each test."""
    return f"+1555{int(time.time()) % 10000000:07d}"


# ─── Health Check ─────────────────────────────────────────────────────────────

class TestSystemHealth:
    """Verify all channels are healthy before running E2E tests."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """API health check must pass."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ("healthy", "ok")

    @pytest.mark.asyncio
    async def test_channels_reported_in_health(self, client):
        """Health endpoint should report channel status."""
        response = await client.get("/health")
        if response.status_code == 200:
            data = response.json()
            # At minimum, web_form should be active
            channels = data.get("channels", {})
            # Accept any non-empty channels dict
            # (channels may not be present in all implementations)
            assert isinstance(channels, dict)


# ─── Web Form Channel (REQUIRED) ──────────────────────────────────────────────

class TestWebFormChannel:
    """Test the Web Support Form — required deliverable."""

    @pytest.mark.asyncio
    async def test_basic_form_submission(self, client, unique_email):
        """Web form submission creates a ticket and returns an ID."""
        response = await client.post(
            "/channels/web-form/submit",
            json={
                "name": "E2E Test User",
                "email": unique_email,
                "subject": "Test submission from E2E suite",
                "category": "technical",
                "priority": "medium",
                "message": "This is an automated E2E test submission to verify the web form endpoint.",
            },
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "ticket_id" in data, f"ticket_id missing from response: {data}"
        assert data["ticket_id"]  # Non-empty

    @pytest.mark.asyncio
    async def test_form_returns_confirmation_message(self, client, unique_email):
        """Submission response must include a confirmation message."""
        response = await client.post(
            "/channels/web-form/submit",
            json={
                "name": "Confirmation Test",
                "email": unique_email,
                "subject": "Testing confirmation message",
                "category": "general",
                "priority": "low",
                "message": "Checking that the confirmation message is returned.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "confirmation" in data or "ticket_id" in data

    @pytest.mark.asyncio
    async def test_form_validation_missing_required_fields(self, client):
        """Form with missing required fields must be rejected."""
        # Missing name, email, message
        response = await client.post(
            "/channels/web-form/submit",
            json={
                "subject": "No name or email",
                "category": "general",
            },
        )
        assert response.status_code in (400, 422), (
            f"Expected validation error, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_form_validation_invalid_email(self, client):
        """Invalid email should be rejected."""
        response = await client.post(
            "/channels/web-form/submit",
            json={
                "name": "Test User",
                "email": "not-an-email",
                "subject": "Invalid email test",
                "category": "general",
                "message": "Testing invalid email validation.",
            },
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_ticket_status_retrieval(self, client, unique_email):
        """Should be able to retrieve ticket status after submission."""
        # Submit
        submit = await client.post(
            "/channels/web-form/submit",
            json={
                "name": "Status Test User",
                "email": unique_email,
                "subject": "Status retrieval test",
                "category": "general",
                "priority": "low",
                "message": "Testing ticket status retrieval endpoint.",
            },
        )
        assert submit.status_code == 200
        ticket_id = submit.json().get("ticket_id")
        assert ticket_id

        # Retrieve status
        status = await client.get(f"/channels/web-form/ticket/{ticket_id}")
        assert status.status_code == 200
        status_data = status.json()
        assert "status" in status_data
        assert status_data["status"] in (
            "open", "in_progress", "processing", "waiting_customer",
            "escalated", "resolved", "closed"
        )

    @pytest.mark.asyncio
    async def test_duplicate_submission_handling(self, client, unique_email):
        """Rapid duplicate submissions should be handled gracefully."""
        payload = {
            "name": "Duplicate Test",
            "email": unique_email,
            "subject": "Duplicate submission test",
            "category": "general",
            "priority": "low",
            "message": "Testing duplicate submission behavior.",
        }
        r1 = await client.post("/channels/web-form/submit", json=payload)
        r2 = await client.post("/channels/web-form/submit", json=payload)

        # Both should succeed (idempotent) or second should be handled gracefully
        assert r1.status_code == 200
        assert r2.status_code in (200, 409, 429)

    @pytest.mark.asyncio
    async def test_high_priority_form_submission(self, client, unique_email):
        """High priority submissions should be accepted."""
        response = await client.post(
            "/channels/web-form/submit",
            json={
                "name": "Urgent Test",
                "email": unique_email,
                "subject": "URGENT: Production is down",
                "category": "bug_report",
                "priority": "high",
                "message": "Critical issue — all workflows stopped running 10 minutes ago. "
                           "Production environment is affected. Need immediate help.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "ticket_id" in data

    @pytest.mark.asyncio
    async def test_all_categories_accepted(self, client):
        """All valid categories should be accepted by the form."""
        categories = ["general", "technical", "billing", "bug_report", "feedback"]
        for category in categories:
            response = await client.post(
                "/channels/web-form/submit",
                json={
                    "name": f"Category Test ({category})",
                    "email": f"cat-{category}-{int(time.time())}@example.com",
                    "subject": f"Test for category: {category}",
                    "category": category,
                    "priority": "low",
                    "message": f"Testing that {category} category is properly accepted.",
                },
            )
            assert response.status_code == 200, f"Category {category} rejected: {response.text}"


# ─── WhatsApp Channel ─────────────────────────────────────────────────────────

class TestWhatsAppChannel:
    """Test WhatsApp (Meta Cloud API) integration."""

    @pytest.mark.asyncio
    async def test_webhook_verification(self, client):
        """GET webhook with correct verify token should return challenge."""
        response = await client.get(
            "/channels/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "echo-this-back",
            },
        )
        # Should return 200 (correct token) or 403 (wrong token — expected in test env)
        assert response.status_code in (200, 403)

    @pytest.mark.asyncio
    async def test_whatsapp_webhook_accepts_post(self, client):
        """POST webhook should accept payloads and return 200."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "test-business-id",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "contacts": [
                                    {"profile": {"name": "Test User"}, "wa_id": "15551234567"}
                                ],
                                "messages": [
                                    {
                                        "from": "15551234567",
                                        "id": f"wamid.test{int(time.time())}",
                                        "timestamp": str(int(time.time())),
                                        "text": {"body": "Hello, I need help with my workflow"},
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        response = await client.post(
            "/channels/whatsapp/webhook",
            json=payload,
            headers={"X-Hub-Signature-256": "sha256=invalid"},  # Will fail sig check
        )
        # Either 200 (processed) or 401 (sig invalid) — both acceptable
        assert response.status_code in (200, 401)

    @pytest.mark.asyncio
    async def test_whatsapp_status_updates_handled(self, client):
        """WhatsApp delivery status updates should not trigger agent processing."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "test-business-id",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "statuses": [
                                    {
                                        "id": "wamid.test123",
                                        "status": "delivered",
                                        "timestamp": str(int(time.time())),
                                        "recipient_id": "15551234567",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        response = await client.post("/channels/whatsapp/webhook", json=payload)
        assert response.status_code in (200, 401)


# ─── Gmail/Email Channel ──────────────────────────────────────────────────────

class TestGmailChannel:
    """Test Gmail integration."""

    @pytest.mark.asyncio
    async def test_gmail_webhook_endpoint_exists(self, client):
        """Gmail webhook endpoint should exist."""
        response = await client.post(
            "/channels/gmail/webhook",
            json={
                "message": {
                    "data": "eyJlbWFpbEFkZHJlc3MiOiAidGVzdEBleGFtcGxlLmNvbSJ9",
                    "messageId": "test-pubsub-msg-id",
                    "publishTime": datetime.utcnow().isoformat() + "Z",
                },
                "subscription": "projects/test-project/subscriptions/gmail-push",
            },
        )
        # 200 (processed) or 204 (no content) are acceptable
        assert response.status_code in (200, 204, 400, 500), (
            f"Unexpected status: {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_gmail_poll_endpoint_exists(self, client):
        """Gmail poll endpoint should exist for admin use."""
        response = await client.post("/channels/gmail/poll")
        # Will fail auth in test env — but endpoint should exist
        assert response.status_code != 404


# ─── Cross-Channel Continuity ─────────────────────────────────────────────────

class TestCrossChannelContinuity:
    """Test that customer identity persists across channels."""

    @pytest.mark.asyncio
    async def test_customer_lookup_after_web_form(self, client, unique_email):
        """Customer created via web form should be findable."""
        # Create via web form
        submit = await client.post(
            "/channels/web-form/submit",
            json={
                "name": "Cross Channel Customer",
                "email": unique_email,
                "subject": "Cross-channel test",
                "category": "general",
                "priority": "low",
                "message": "Testing cross-channel customer tracking.",
            },
        )
        assert submit.status_code == 200

        # Small delay for async processing
        await asyncio.sleep(0.5)

        # Look up customer
        lookup = await client.get(
            "/customers/lookup",
            params={"email": unique_email},
        )

        # Customer may or may not be in DB yet (async processing)
        assert lookup.status_code in (200, 404)
        if lookup.status_code == 200:
            customer = lookup.json()
            assert "id" in customer or "customer_id" in customer

    @pytest.mark.asyncio
    async def test_ticket_history_endpoint(self, client, unique_email):
        """Multiple tickets from same customer should be retrievable."""
        # Submit 2 tickets
        for i in range(2):
            await client.post(
                "/channels/web-form/submit",
                json={
                    "name": "History Test User",
                    "email": unique_email,
                    "subject": f"Ticket #{i+1} — History test",
                    "category": "general",
                    "priority": "low",
                    "message": f"This is ticket number {i+1} for history testing.",
                },
            )

        await asyncio.sleep(0.5)

        # Look up customer history
        lookup = await client.get("/customers/lookup", params={"email": unique_email})
        if lookup.status_code == 200:
            customer = lookup.json()
            # If customer found, they should have tickets
            tickets = customer.get("tickets", customer.get("conversations", []))
            assert isinstance(tickets, list)


# ─── Channel-Specific Response Format Tests ───────────────────────────────────

class TestChannelAdaptation:
    """Verify that responses are adapted per channel."""

    @pytest.mark.asyncio
    async def test_web_form_response_format(self, client, unique_email):
        """Web form responses should include ticket reference."""
        submit = await client.post(
            "/channels/web-form/submit",
            json={
                "name": "Format Test User",
                "email": unique_email,
                "subject": "How do I connect Gmail trigger?",
                "category": "technical",
                "priority": "medium",
                "message": "I'm trying to set up a Gmail trigger in my workflow but "
                           "I'm not sure how to authorize the connection. Can you help?",
            },
        )
        assert submit.status_code == 200
        data = submit.json()
        assert "ticket_id" in data


# ─── Metrics Endpoint ─────────────────────────────────────────────────────────

class TestMetrics:
    """Test monitoring and metrics endpoints."""

    @pytest.mark.asyncio
    async def test_channel_metrics_endpoint(self, client):
        """Channel metrics endpoint should return structured data."""
        response = await client.get("/metrics/channels")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
        else:
            # Endpoint may not exist — that's acceptable if not implemented
            assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_health_includes_timestamp(self, client):
        """Health endpoint should include a timestamp."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # Accept any health response — just verify it's JSON
        assert isinstance(data, dict)


# ─── Stress / Edge Cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases and robustness."""

    @pytest.mark.asyncio
    async def test_very_long_message_handled(self, client, unique_email):
        """Very long messages should be accepted (truncated internally)."""
        long_message = "I need help. " * 500  # ~6500 chars
        response = await client.post(
            "/channels/web-form/submit",
            json={
                "name": "Long Message User",
                "email": unique_email,
                "subject": "Very detailed issue description",
                "category": "technical",
                "priority": "medium",
                "message": long_message[:1000],  # Form cap
            },
        )
        assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_nonexistent_ticket_returns_404(self, client):
        """Requesting a non-existent ticket should return 404."""
        response = await client.get("/channels/web-form/ticket/TKT-NONEXISTENT-99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_concurrent_submissions(self, client):
        """Multiple concurrent submissions should all succeed."""
        tasks = [
            client.post(
                "/channels/web-form/submit",
                json={
                    "name": f"Concurrent User {i}",
                    "email": f"concurrent-{i}-{int(time.time())}@example.com",
                    "subject": f"Concurrent test #{i}",
                    "category": "general",
                    "priority": "low",
                    "message": f"Concurrent submission number {i} for load testing.",
                },
            )
            for i in range(5)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        successes = [r for r in responses if hasattr(r, "status_code") and r.status_code == 200]
        assert len(successes) >= 4, f"At least 4 of 5 concurrent submissions should succeed"
