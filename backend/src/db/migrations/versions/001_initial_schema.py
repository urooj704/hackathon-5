"""Initial schema — customers, tickets, messages, escalations, doc_chunks

Revision ID: 001
Revises:
Create Date: 2026-02-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Enums ─────────────────────────────────────────────────────────────────
    op.execute(
        "CREATE TYPE IF NOT EXISTS channel_enum AS ENUM ('email', 'whatsapp', 'web_form')"
    )
    op.execute(
        "CREATE TYPE IF NOT EXISTS ticket_status_enum AS ENUM "
        "('open', 'in_progress', 'waiting_customer', 'escalated', 'resolved', 'closed')"
    )
    op.execute(
        "CREATE TYPE IF NOT EXISTS ticket_urgency_enum AS ENUM ('low', 'medium', 'high', 'critical')"
    )
    op.execute(
        "CREATE TYPE IF NOT EXISTS sentiment_enum AS ENUM "
        "('positive', 'neutral', 'confused', 'frustrated', 'anxious', 'angry', 'furious')"
    )
    op.execute(
        "CREATE TYPE IF NOT EXISTS escalation_tier_enum AS ENUM ('tier_1', 'tier_2', 'tier_3')"
    )
    op.execute(
        "CREATE TYPE IF NOT EXISTS plan_enum AS ENUM "
        "('starter', 'growth', 'business', 'enterprise', 'trial', 'unknown')"
    )

    # ── customers ─────────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "plan",
            sa.Enum(
                "starter", "growth", "business", "enterprise", "trial", "unknown",
                name="plan_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("gdpr_region", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_enterprise", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("csm_assigned", sa.String(255), nullable=True),
        sa.Column("churn_risk", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("lifetime_tickets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_sentiment_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_index("ix_customers_phone", "customers", ["phone"])

    # ── tickets ───────────────────────────────────────────────────────────────
    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("display_id", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open", "in_progress", "waiting_customer",
                "escalated", "resolved", "closed",
                name="ticket_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "urgency",
            sa.Enum(
                "low", "medium", "high", "critical",
                name="ticket_urgency_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("intent", sa.String(100), nullable=True),
        sa.Column(
            "origin_channel",
            sa.Enum(
                "email", "whatsapp", "web_form",
                name="channel_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ai_suggested_resolution", sa.Text(), nullable=True),
        sa.Column(
            "latest_sentiment",
            sa.Enum(
                "positive", "neutral", "confused", "frustrated",
                "anxious", "angry", "furious",
                name="sentiment_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_id"),
    )
    op.create_index("ix_tickets_customer_id", "tickets", ["customer_id"])
    op.create_index("ix_tickets_display_id", "tickets", ["display_id"])

    # ── messages ──────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("is_from_customer", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "channel",
            sa.Enum(
                "email", "whatsapp", "web_form",
                name="channel_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("channel_message_id", sa.String(512), nullable=True),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("attachment_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "detected_sentiment",
            sa.Enum(
                "positive", "neutral", "confused", "frustrated",
                "anxious", "angry", "furious",
                name="sentiment_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("detected_intent", sa.String(100), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            index=True,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_ticket_created", "messages", ["ticket_id", "created_at"])
    op.create_index("ix_messages_channel_msg_id", "messages", ["channel_message_id"])

    # ── escalations ───────────────────────────────────────────────────────────
    op.create_table(
        "escalations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "tier",
            sa.Enum(
                "tier_1", "tier_2", "tier_3",
                name="escalation_tier_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("trigger_keywords", postgresql.JSONB(), nullable=True),
        sa.Column("routed_to", sa.String(255), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("acknowledged_by", sa.String(255), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_escalations_ticket_id", "escalations", ["ticket_id"])

    # ── doc_chunks ────────────────────────────────────────────────────────────
    op.create_table(
        "doc_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("section_title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", sa.Text(), nullable=True),  # pgvector type via raw SQL
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add vector column and index using raw SQL (pgvector not natively in Alembic)
    op.execute("ALTER TABLE doc_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
    op.execute(
        "CREATE INDEX ix_doc_chunks_embedding_cosine ON doc_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)"
    )


def downgrade() -> None:
    op.drop_table("doc_chunks")
    op.drop_table("escalations")
    op.drop_table("messages")
    op.drop_table("tickets")
    op.drop_table("customers")

    op.execute("DROP TYPE IF EXISTS escalation_tier_enum")
    op.execute("DROP TYPE IF EXISTS plan_enum")
    op.execute("DROP TYPE IF EXISTS sentiment_enum")
    op.execute("DROP TYPE IF EXISTS ticket_urgency_enum")
    op.execute("DROP TYPE IF EXISTS ticket_status_enum")
    op.execute("DROP TYPE IF EXISTS channel_enum")
