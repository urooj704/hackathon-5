"""
FlowForge Customer Success Agent — FastAPI application entry point.

Startup sequence:
  1. Init DB (create tables, enable pgvector extension)
  2. Load knowledge base into doc_chunks (skipped if already loaded)
  3. Register channel routers

Run with:
  uvicorn src.app:app --reload --port 8000
"""

from __future__ import annotations

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.db.connection import get_db, init_db
from src.knowledge.loader import load_knowledge_base

log = structlog.get_logger(__name__)
settings = get_settings()


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before serving requests."""
    log.info("app_starting", env=settings.app_env)

    # Initialize database tables
    await init_db()
    log.info("db_initialized")

    # Load knowledge base (no-op if already loaded)
    async with get_db() as db:
        chunks = await load_knowledge_base(db)
        if chunks:
            log.info("knowledge_base_loaded", chunks=chunks)
        else:
            log.info("knowledge_base_already_loaded")

    log.info("app_ready")
    yield
    log.info("app_stopping")


# ─── App factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="FlowForge Customer Success Agent",
        description="Multi-channel AI support agent for FlowForge",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # CORS (restrict in production)
    origins = ["*"] if not settings.is_production else ["https://flowforge.io"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Channel routers
    from src.channels.gmail import router as gmail_router
    from src.channels.whatsapp import router as whatsapp_router
    from src.channels.web_form import router as web_form_router

    app.include_router(gmail_router)
    app.include_router(whatsapp_router)
    app.include_router(web_form_router)

    # ── Health / utility endpoints ────────────────────────────────────────────

    @app.get("/health", tags=["ops"])
    async def health():
        from datetime import datetime, timezone
        return {
            "status": "healthy",
            "env": settings.app_env,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channels": {
                "email": "active",
                "whatsapp": "active",
                "web_form": "active",
            },
        }

    @app.get("/health/db", tags=["ops"])
    async def health_db():
        """Check DB connectivity."""
        from sqlalchemy import text

        try:
            async with get_db() as db:
                await db.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception as exc:
            return JSONResponse(status_code=503, content={"status": "error", "detail": str(exc)})

    @app.post("/admin/kb/reload", tags=["admin"])
    async def reload_knowledge_base():
        """Force reload of the knowledge base from product-docs.md."""
        async with get_db() as db:
            chunks = await load_knowledge_base(db, force_reload=True)
        return {"status": "ok", "chunks_loaded": chunks}

    # ── Customer lookup ───────────────────────────────────────────────────────

    @app.get("/customers/lookup", tags=["customers"])
    async def lookup_customer(email: str = None, phone: str = None):
        """Look up a customer by email or phone across all channels."""
        if not email and not phone:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Provide email or phone parameter")

        from sqlalchemy import select
        from src.db.models import Customer, Ticket

        async with get_db() as db:
            if email:
                result = await db.execute(
                    select(Customer).where(Customer.email == email)
                )
            else:
                result = await db.execute(
                    select(Customer).where(Customer.phone == phone)
                )
            customer = result.scalar_one_or_none()

        if customer is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Customer not found")

        async with get_db() as db:
            tickets_result = await db.execute(
                select(Ticket)
                .where(Ticket.customer_id == customer.id)
                .order_by(Ticket.created_at.desc())
                .limit(20)
            )
            tickets = tickets_result.scalars().all()

        return {
            "id": customer.id,
            "email": customer.email,
            "phone": customer.phone,
            "name": customer.name,
            "plan": customer.plan.value if hasattr(customer.plan, "value") else str(customer.plan),
            "lifetime_tickets": customer.lifetime_tickets,
            "conversations": [
                {
                    "ticket_id": t.display_id,
                    "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                    "channel": t.origin_channel.value if hasattr(t.origin_channel, "value") else str(t.origin_channel),
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tickets
            ],
        }

    # ── Channel metrics ───────────────────────────────────────────────────────

    @app.get("/metrics/channels", tags=["ops"])
    async def channel_metrics():
        """Get performance metrics broken down by channel (last 24 hours)."""
        from sqlalchemy import text

        try:
            async with get_db() as db:
                result = await db.execute(
                    text("""
                        SELECT
                            origin_channel AS channel,
                            COUNT(*) AS total_tickets,
                            COUNT(*) FILTER (WHERE status = 'escalated') AS escalations,
                            COUNT(*) FILTER (WHERE status = 'resolved') AS resolved,
                            AVG(CASE WHEN latest_sentiment IS NOT NULL
                                THEN CASE latest_sentiment
                                    WHEN 'positive' THEN 1
                                    WHEN 'neutral' THEN 0
                                    WHEN 'confused' THEN -0.5
                                    WHEN 'frustrated' THEN -1
                                    WHEN 'anxious' THEN -1.5
                                    WHEN 'angry' THEN -2
                                    WHEN 'furious' THEN -3
                                    ELSE 0 END
                                ELSE NULL END) AS avg_sentiment
                        FROM tickets
                        WHERE created_at > NOW() - INTERVAL '24 hours'
                        GROUP BY origin_channel
                    """)
                )
                rows = result.mappings().all()

            return {
                row["channel"]: {
                    "total_conversations": row["total_tickets"],
                    "escalations": row["escalations"],
                    "resolved": row["resolved"],
                    "avg_sentiment": round(float(row["avg_sentiment"]), 2) if row["avg_sentiment"] else None,
                    "escalation_rate": round(row["escalations"] / row["total_tickets"], 3) if row["total_tickets"] > 0 else 0,
                }
                for row in rows
            }
        except Exception as exc:
            log.error("metrics_error", error=str(exc))
            return {"email": {}, "whatsapp": {}, "web_form": {}}

    return app


app = create_app()
