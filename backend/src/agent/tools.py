"""
Tool definitions for the FlowForge AI Agent (Claude tool use).

These are the actions the agent can take:
  - search_docs       : Semantic search over the knowledge base
  - create_ticket     : Create a new support ticket
  - update_ticket     : Update ticket status/urgency/summary
  - escalate          : Route ticket to human agent
  - check_status_page : Check if there's a known outage

Tools follow the Anthropic tool use schema.
"""

from typing import Any

# ─── Tool Schemas (passed to Claude) ─────────────────────────────────────────

TOOLS = [
    {
        "name": "search_docs",
        "description": (
            "Search the FlowForge product documentation and knowledge base "
            "for information relevant to the customer's question. "
            "Always use this before answering technical or product questions. "
            "Use a specific, descriptive query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Specific search query, e.g. 'Airtable Personal Access Token setup' or 'Gmail trigger not firing polling interval'",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_ticket",
        "description": (
            "Create a new support ticket for the current conversation. "
            "Call this at the start of a new issue that doesn't have an existing ticket. "
            "Returns the ticket display ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": [
                        "technical_support",
                        "billing_dispute",
                        "billing_admin",
                        "billing_inquiry",
                        "how_to",
                        "product_inquiry",
                        "product_evaluation",
                        "compliance_request",
                        "security_incident",
                        "legal_request",
                        "escalation",
                        "cancellation",
                        "retention",
                        "feature_request",
                        "trial_inquiry",
                        "enterprise_sales",
                        "partnership_inquiry",
                        "outage_inquiry",
                        "follow_up",
                        "other",
                    ],
                    "description": "The classified intent of the customer's message.",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Urgency level based on business impact and customer sentiment.",
                },
                "summary": {
                    "type": "string",
                    "description": "One-sentence summary of the issue, e.g. 'HubSpot OAuth token expired, workflow not running'",
                },
            },
            "required": ["intent", "urgency", "summary"],
        },
    },
    {
        "name": "update_ticket",
        "description": (
            "Update an existing ticket's status, urgency, or summary. "
            "Use when the situation changes (e.g., customer provides more info, "
            "issue is resolved, urgency increases)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "open",
                        "in_progress",
                        "waiting_customer",
                        "escalated",
                        "resolved",
                    ],
                    "description": "New status for the ticket.",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Updated urgency if it has changed.",
                },
                "summary": {
                    "type": "string",
                    "description": "Updated one-sentence summary of the current state.",
                },
                "resolution_notes": {
                    "type": "string",
                    "description": "If resolving: brief note on how it was resolved.",
                },
            },
            "required": [],  # All fields optional — only update what changed
        },
    },
    {
        "name": "escalate",
        "description": (
            "Escalate the current ticket to a human agent. "
            "Use whenever escalation rules are triggered. "
            "This routes the ticket to the appropriate team and logs the escalation event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "enum": ["tier_1", "tier_2", "tier_3"],
                    "description": (
                        "tier_1: Immediate, no AI resolution (security/legal/HIPAA/chargeback). "
                        "tier_2: AI responded once, human follow-up needed (refunds/angry/outage/data loss). "
                        "tier_3: Flag for review only (feature requests/partnerships)."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "Human-readable reason for escalation, e.g. 'Customer threatened chargeback and cancellation'",
                },
                "route_to": {
                    "type": "string",
                    "enum": [
                        "billing@flowforge.io",
                        "security@flowforge.io",
                        "legal@flowforge.io",
                        "sales@flowforge.io",
                        "partnerships@flowforge.io",
                        "pr@flowforge.io",
                        "engineering_oncall",
                        "human_queue",
                    ],
                    "description": "Which team or queue to route the escalation to.",
                },
                "trigger_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords from the customer message that triggered the escalation rule.",
                },
            },
            "required": ["tier", "reason", "route_to"],
        },
    },
    {
        "name": "check_status_page",
        "description": (
            "Check if there is a known active incident on the FlowForge status page. "
            "Always call this when a customer reports that workflows aren't running, "
            "the platform seems down, or triggers aren't firing unexpectedly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ─── Tool Executors ────────────────────────────────────────────────────────────

async def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    context: "AgentContext",  # type: ignore[name-defined] — defined in core.py
) -> str:
    """
    Route tool calls to their implementations.
    Returns a string result that gets fed back to Claude.
    """
    from src.agent.tool_handlers import (
        handle_search_docs,
        handle_create_ticket,
        handle_update_ticket,
        handle_escalate,
        handle_check_status_page,
    )

    handlers = {
        "search_docs": handle_search_docs,
        "create_ticket": handle_create_ticket,
        "update_ticket": handle_update_ticket,
        "escalate": handle_escalate,
        "check_status_page": handle_check_status_page,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return f"Unknown tool: {tool_name}"

    return await handler(tool_input, context)
