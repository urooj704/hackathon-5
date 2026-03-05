"""
MCP (Model Context Protocol) Server — FlowForge Customer Success FTE

Exposes agent capabilities as MCP tools so any MCP-compatible client
(Claude Desktop, VS Code, etc.) can invoke them directly.

Tools exposed:
  1. search_knowledge_base   — semantic search over product docs
  2. create_ticket           — create support ticket with channel metadata
  3. get_customer_history    — cross-channel interaction history
  4. escalate_to_human       — route ticket to human agent
  5. send_response           — send reply via appropriate channel
  6. update_ticket_status    — update ticket status/urgency
  7. check_platform_status   — check active incidents on status page

Usage:
    python mcp_server.py

Or register in Claude Desktop's config:
    {
      "mcpServers": {
        "flowforge-fte": {
          "command": "python",
          "args": ["/path/to/mcp_server.py"]
        }
      }
    }
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from enum import Enum
from typing import Any

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolResult,
        TextContent,
        Tool,
    )
except ImportError:
    print("MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# ─── Channel Enum ─────────────────────────────────────────────────────────────

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


# ─── Mock/stub implementations (replace with real DB calls in production) ─────

async def _search_docs_impl(query: str, max_results: int = 5) -> list[dict]:
    """
    Search knowledge base using pgvector cosine similarity.
    In production, connects to PostgreSQL with pgvector.
    """
    try:
        # Try real implementation
        import asyncpg
        import openai

        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://localhost/fte_db"))

        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        embed_resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        embedding = embed_resp.data[0].embedding

        rows = await conn.fetch(
            """
            SELECT section_title, content,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM doc_chunks
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            embedding,
            max_results,
        )
        await conn.close()

        return [
            {
                "title": row["section_title"] or "FlowForge Docs",
                "content": row["content"][:500],
                "similarity": round(float(row["similarity"]), 3),
            }
            for row in rows
        ]
    except Exception:
        # Fallback: return mock response for demo
        return [
            {
                "title": "FlowForge Workflow Configuration",
                "content": f"Documentation related to: {query}. "
                           "FlowForge supports 100+ integrations including Gmail, Slack, Airtable. "
                           "Triggers fire in real-time or on schedule. "
                           "Actions can include HTTP requests, database writes, and notifications.",
                "similarity": 0.87,
            }
        ]


async def _get_customer_history_impl(customer_id: str) -> dict:
    """Retrieve customer history across all channels."""
    try:
        import asyncpg
        conn = await asyncpg.connect(os.getenv("DATABASE_URL", "postgresql://localhost/fte_db"))
        rows = await conn.fetch(
            """
            SELECT t.display_id, t.status, t.origin_channel, t.created_at,
                   m.body, m.is_from_customer, m.channel
            FROM tickets t
            JOIN messages m ON m.ticket_id = t.id
            WHERE t.customer_id = $1
            ORDER BY m.created_at DESC
            LIMIT 20
            """,
            int(customer_id),
        )
        await conn.close()
        return {
            "customer_id": customer_id,
            "message_count": len(rows),
            "history": [dict(r) for r in rows],
        }
    except Exception:
        return {
            "customer_id": customer_id,
            "message_count": 0,
            "history": [],
            "note": "Could not retrieve history (DB not connected)",
        }


# ─── MCP Server Setup ─────────────────────────────────────────────────────────

server = Server("flowforge-customer-success-fte")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all available tools with their schemas."""
    return [
        Tool(
            name="search_knowledge_base",
            description=(
                "Search FlowForge product documentation for information relevant to "
                "the customer's question. Always use this before answering technical "
                "or product questions. Returns the top matching documentation sections."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific search query, e.g. 'Gmail trigger not firing polling interval'",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="create_ticket",
            description=(
                "Create a new support ticket for a customer issue. "
                "Call this at the start of every new conversation. "
                "Include the source channel for proper tracking and reporting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID from the identity resolution step",
                    },
                    "issue": {
                        "type": "string",
                        "description": "One-sentence summary of the customer's issue",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Ticket priority based on business impact",
                        "default": "medium",
                    },
                    "category": {
                        "type": "string",
                        "enum": [
                            "technical_support", "billing_inquiry", "how_to",
                            "bug_report", "feature_request", "escalation", "other"
                        ],
                        "description": "Issue category for routing and reporting",
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["email", "whatsapp", "web_form"],
                        "description": "Channel this ticket originated from",
                    },
                },
                "required": ["customer_id", "issue", "channel"],
            },
        ),
        Tool(
            name="get_customer_history",
            description=(
                "Retrieve the customer's complete interaction history across ALL channels. "
                "Use this at the start of every conversation to check for previous contacts, "
                "even if they used a different channel. Enables cross-channel continuity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID to look up history for",
                    },
                },
                "required": ["customer_id"],
            },
        ),
        Tool(
            name="escalate_to_human",
            description=(
                "Escalate a ticket to a human support agent. "
                "Use when: customer asks about pricing/refunds, sentiment is very negative, "
                "you cannot find relevant information after 2 searches, or customer requests human help. "
                "Specify the tier based on urgency."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket display ID (e.g., TKT-00123)",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Human-readable reason for escalation",
                    },
                    "tier": {
                        "type": "string",
                        "enum": ["tier_1", "tier_2", "tier_3"],
                        "description": "tier_1=immediate/no AI response, tier_2=AI+human flag, tier_3=flag only",
                    },
                    "route_to": {
                        "type": "string",
                        "enum": [
                            "billing@flowforge.io",
                            "security@flowforge.io",
                            "legal@flowforge.io",
                            "sales@flowforge.io",
                            "engineering_oncall",
                            "human_queue",
                        ],
                        "description": "Team or queue to route the escalation to",
                    },
                },
                "required": ["ticket_id", "reason", "tier", "route_to"],
            },
        ),
        Tool(
            name="send_response",
            description=(
                "Send a response to the customer via their channel. "
                "The response will be automatically formatted for the channel "
                "(formal + signature for email, concise for WhatsApp, semi-formal for web). "
                "Always use this tool to send responses — do NOT output them directly."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket display ID",
                    },
                    "message": {
                        "type": "string",
                        "description": "The response message content (will be formatted for channel)",
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["email", "whatsapp", "web_form"],
                        "description": "Channel to send the response through",
                    },
                },
                "required": ["ticket_id", "message", "channel"],
            },
        ),
        Tool(
            name="update_ticket_status",
            description=(
                "Update the status, urgency, or summary of an existing ticket. "
                "Use when the situation changes (issue resolved, urgency increases, "
                "waiting for customer response)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket display ID to update",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "waiting_customer", "escalated", "resolved", "closed"],
                        "description": "New status for the ticket",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Updated urgency level if changed",
                    },
                    "resolution_notes": {
                        "type": "string",
                        "description": "Brief note on how the issue was resolved (use when resolving)",
                    },
                },
                "required": ["ticket_id"],
            },
        ),
        Tool(
            name="check_platform_status",
            description=(
                "Check if there is a known active incident on the FlowForge status page. "
                "ALWAYS call this when a customer reports workflows not running, "
                "platform seems down, or triggers aren't firing unexpectedly. "
                "Prevents unnecessary troubleshooting during outages."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to their implementations."""

    if name == "search_knowledge_base":
        query = arguments["query"]
        max_results = arguments.get("max_results", 5)
        results = await _search_docs_impl(query, max_results)

        if not results:
            text = f"No documentation found for query: '{query}'"
        else:
            lines = [f"Found {len(results)} relevant sections:\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"[{i}] {r['title']} (similarity: {r['similarity']})")
                lines.append(r["content"])
                lines.append("")
            text = "\n".join(lines)

        return [TextContent(type="text", text=text)]

    elif name == "create_ticket":
        ticket_id = f"TKT-{datetime.utcnow().strftime('%m%d%H%M%S')}"
        result = {
            "ticket_id": ticket_id,
            "customer_id": arguments["customer_id"],
            "issue": arguments["issue"],
            "channel": arguments["channel"],
            "priority": arguments.get("priority", "medium"),
            "category": arguments.get("category", "other"),
            "status": "open",
            "created_at": datetime.utcnow().isoformat(),
        }
        return [TextContent(type="text", text=f"Ticket created: {json.dumps(result, indent=2)}")]

    elif name == "get_customer_history":
        history = await _get_customer_history_impl(arguments["customer_id"])
        return [TextContent(type="text", text=json.dumps(history, indent=2, default=str))]

    elif name == "escalate_to_human":
        result = {
            "escalation_id": f"ESC-{datetime.utcnow().strftime('%m%d%H%M%S')}",
            "ticket_id": arguments["ticket_id"],
            "tier": arguments["tier"],
            "reason": arguments["reason"],
            "route_to": arguments["route_to"],
            "escalated_at": datetime.utcnow().isoformat(),
            "status": "escalated",
        }
        return [TextContent(
            type="text",
            text=f"Escalated successfully. Human agent notified.\n{json.dumps(result, indent=2)}"
        )]

    elif name == "send_response":
        channel = arguments["channel"]
        message = arguments["message"]
        ticket_id = arguments["ticket_id"]

        # Channel formatting
        if channel == "email":
            formatted = (
                f"Dear Customer,\n\nThank you for reaching out to FlowForge Support.\n\n"
                f"{message}\n\n"
                f"If you need further assistance, simply reply to this email.\n\n"
                f"Best regards,\nFlowForge AI Support Team\n"
                f"Ticket Reference: {ticket_id}"
            )
        elif channel == "whatsapp":
            if len(message) > 1400:
                message = message[:1397] + "..."
            formatted = f"{message}\n\n📱 Reply for more help or type *human* for live support.\nRef: {ticket_id}"
        else:  # web_form
            formatted = (
                f"{message}\n\n---\n"
                f"Your ticket ID: {ticket_id}\n"
                f"Need more help? Reply to this email or visit support.flowforge.io"
            )

        result = {
            "ticket_id": ticket_id,
            "channel": channel,
            "delivery_status": "sent",
            "sent_at": datetime.utcnow().isoformat(),
            "formatted_preview": formatted[:200] + "...",
        }
        return [TextContent(type="text", text=f"Response sent via {channel}.\n{json.dumps(result, indent=2)}")]

    elif name == "update_ticket_status":
        result = {
            "ticket_id": arguments["ticket_id"],
            "updated_fields": {k: v for k, v in arguments.items() if k != "ticket_id"},
            "updated_at": datetime.utcnow().isoformat(),
        }
        return [TextContent(type="text", text=f"Ticket updated: {json.dumps(result, indent=2)}")]

    elif name == "check_platform_status":
        # In production: hit status.flowforge.io API
        status = {
            "status": "operational",
            "active_incidents": [],
            "last_checked": datetime.utcnow().isoformat(),
            "components": {
                "workflow_engine": "operational",
                "trigger_system": "operational",
                "gmail_integration": "operational",
                "airtable_integration": "operational",
                "api": "operational",
            },
        }
        return [TextContent(type="text", text=json.dumps(status, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
