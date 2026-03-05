"""
Load Test — FlowForge Customer Success FTE
Uses Locust for distributed load testing.

Simulates real-world traffic across all channels to verify 24/7 readiness.

Install:
    pip install locust

Run (local):
    locust -f tests/load_test.py --host=http://localhost:8000

Run (headless — 10 users, 2 min):
    locust -f tests/load_test.py --host=http://localhost:8000 \\
           --users 10 --spawn-rate 2 --run-time 2m --headless

Production load test (100 users):
    locust -f tests/load_test.py --host=https://support-api.flowforge.io \\
           --users 100 --spawn-rate 5 --run-time 24h --headless \\
           --html report.html
"""

import random
import time
from locust import HttpUser, TaskSet, between, task, events


# ─── Shared data pools ────────────────────────────────────────────────────────

SAMPLE_NAMES = [
    "Alice Johnson", "Bob Smith", "Carol White", "David Brown",
    "Eve Davis", "Frank Wilson", "Grace Lee", "Henry Taylor",
]

SAMPLE_SUBJECTS = [
    "Gmail trigger not firing",
    "How to connect Airtable",
    "Workflow runs but no output",
    "Billing question about upgrade",
    "Can't authenticate with HubSpot",
    "Need help setting up Slack notifications",
    "Zapier vs FlowForge comparison",
    "Webhook not receiving data",
    "How to use conditional logic",
    "API authentication setup",
]

SAMPLE_MESSAGES = [
    "I've set up a Gmail trigger but it's not firing when new emails arrive. I've checked the filters and everything looks correct.",
    "I'm trying to connect my Airtable base but keep getting an authorization error. I've already generated a Personal Access Token.",
    "My workflow shows as running in the logs but the output step isn't executing. No errors in the dashboard.",
    "I'm on the Starter plan and considering upgrading to Growth. What's included and how does billing work?",
    "The HubSpot integration keeps asking me to re-authenticate every few hours. Is this normal?",
    "I want to send Slack notifications when a Google Form is submitted. What's the best way to set this up?",
    "Can you explain the main differences between FlowForge and Zapier for someone evaluating both?",
    "My webhook endpoint is configured correctly in the dashboard but I'm not receiving POST requests.",
    "How do I add conditional logic to only run certain steps when specific conditions are met?",
    "I need help understanding how to authenticate API calls within my workflow steps.",
]

CATEGORIES = ["general", "technical", "billing", "bug_report", "feedback"]
PRIORITIES = ["low", "medium", "high"]


def random_email():
    return f"loadtest{random.randint(1, 100000)}@example.com"


def random_phone():
    return f"+1555{random.randint(1000000, 9999999)}"


# ─── Task Sets ────────────────────────────────────────────────────────────────

class WebFormTasks(TaskSet):
    """Simulate web form submissions — the primary channel."""

    @task(5)
    def submit_support_form(self):
        """Submit a standard support form."""
        with self.client.post(
            "/channels/web-form/submit",
            json={
                "name": random.choice(SAMPLE_NAMES),
                "email": random_email(),
                "subject": random.choice(SAMPLE_SUBJECTS),
                "category": random.choice(CATEGORIES),
                "priority": random.choice(PRIORITIES),
                "message": random.choice(SAMPLE_MESSAGES),
            },
            catch_response=True,
            name="POST /channels/web-form/submit",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "ticket_id" in data:
                    response.success()
                    # Store ticket ID for follow-up test
                    self.user.last_ticket_id = data["ticket_id"]
                else:
                    response.failure("No ticket_id in response")
            elif response.status_code == 422:
                response.failure("Validation error — check payload")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def check_ticket_status(self):
        """Check ticket status after submission."""
        ticket_id = getattr(self.user, "last_ticket_id", None)
        if not ticket_id:
            return

        with self.client.get(
            f"/channels/web-form/ticket/{ticket_id}",
            catch_response=True,
            name="GET /channels/web-form/ticket/{id}",
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def submit_high_priority(self):
        """Simulate urgent/high-priority submissions."""
        with self.client.post(
            "/channels/web-form/submit",
            json={
                "name": random.choice(SAMPLE_NAMES),
                "email": random_email(),
                "subject": "URGENT: Production workflows stopped",
                "category": "bug_report",
                "priority": "high",
                "message": "All our production workflows have stopped running. "
                           "This is a critical issue affecting our business operations. "
                           "We process 500+ workflows per day and everything is stuck.",
            },
            catch_response=True,
            name="POST /channels/web-form/submit [high-priority]",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"High priority submission failed: {response.status_code}")


class HealthCheckTasks(TaskSet):
    """Monitor system health during load test."""

    @task(3)
    def check_health(self):
        """Basic health check."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="GET /health",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") in ("healthy", "ok"):
                    response.success()
                else:
                    response.failure(f"Unhealthy status: {data.get('status')}")
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(1)
    def check_channel_metrics(self):
        """Check channel-specific metrics."""
        with self.client.get(
            "/metrics/channels",
            catch_response=True,
            name="GET /metrics/channels",
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Metrics failed: {response.status_code}")


class CustomerLookupTasks(TaskSet):
    """Test customer lookup endpoints."""

    @task
    def lookup_random_customer(self):
        """Look up a random customer (most will be 404)."""
        with self.client.get(
            "/customers/lookup",
            params={"email": random_email()},
            catch_response=True,
            name="GET /customers/lookup",
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            elif response.status_code == 400:
                response.failure("Bad request to customer lookup")
            else:
                response.failure(f"Unexpected: {response.status_code}")


# ─── User classes ─────────────────────────────────────────────────────────────

class WebFormUser(HttpUser):
    """
    Primary user type — simulates customers using the support form.
    Highest weight: web form is the most common channel.
    """
    tasks = [WebFormTasks]
    wait_time = between(2, 10)
    weight = 5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_ticket_id = None


class MonitoringUser(HttpUser):
    """
    Simulates health check monitoring (uptime robots, dashboards).
    Low weight: monitoring is infrequent.
    """
    tasks = [HealthCheckTasks]
    wait_time = between(10, 30)
    weight = 1


class AdminUser(HttpUser):
    """
    Simulates admin operations (customer lookups, metrics checks).
    Low weight.
    """
    tasks = [CustomerLookupTasks]
    wait_time = between(5, 20)
    weight = 1


# ─── Custom events for reporting ─────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "="*60)
    print("FlowForge FTE Load Test Starting")
    print(f"Target: {environment.host}")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats.total
    print("\n" + "="*60)
    print("Load Test Complete — Summary")
    print(f"Total requests:    {stats.num_requests}")
    print(f"Failures:          {stats.num_failures}")
    print(f"Failure rate:      {stats.fail_ratio:.1%}")
    print(f"Avg response time: {stats.avg_response_time:.0f}ms")
    print(f"P95 response time: {stats.get_response_time_percentile(0.95):.0f}ms")
    print(f"P99 response time: {stats.get_response_time_percentile(0.99):.0f}ms")
    print(f"RPS:               {stats.current_rps:.1f}")
    print("="*60)

    # Validate SLA targets
    p95 = stats.get_response_time_percentile(0.95)
    fail_rate = stats.fail_ratio

    sla_pass = True
    if p95 > 3000:
        print(f"❌ SLA VIOLATION: P95 latency {p95:.0f}ms > 3000ms target")
        sla_pass = False
    if fail_rate > 0.01:
        print(f"❌ SLA VIOLATION: Failure rate {fail_rate:.1%} > 1% target")
        sla_pass = False

    if sla_pass:
        print("✅ All SLA targets met!")
    print("="*60 + "\n")
