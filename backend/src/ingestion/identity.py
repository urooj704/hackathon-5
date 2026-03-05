"""
Customer Identity Resolver.

Resolves a NormalizedMessage to a unified Customer record in PostgreSQL.
Strategy:
  1. Email match (primary key) — exact match
  2. Phone match (secondary key) — exact match
  3. No match → create new Customer record

After resolution, the customer record is enriched with any new info from the message.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import (
    create_customer,
    get_customer_by_email,
    get_customer_by_phone,
    update_customer,
)
from src.db.models import Customer
from src.ingestion.normalizer import NormalizedMessage

log = structlog.get_logger(__name__)


async def resolve_customer(
    db: AsyncSession,
    message: NormalizedMessage,
) -> Customer:
    """
    Given a NormalizedMessage, find or create the corresponding Customer.

    Resolution order:
      1. Try email lookup
      2. Try phone lookup
      3. Create new record

    Also handles enrichment: if we find the customer by email but they now
    have a phone (WhatsApp message), we update their record.
    """
    customer: Customer | None = None

    # ── Step 1: Try email ────────────────────────────────────────────────────
    if message.customer_email:
        customer = await get_customer_by_email(db, message.customer_email)
        if customer:
            log.info(
                "customer_resolved_by_email",
                customer_id=customer.id,
                email=message.customer_email,
            )

    # ── Step 2: Try phone (if no email match) ────────────────────────────────
    if customer is None and message.customer_phone:
        customer = await get_customer_by_phone(db, message.customer_phone)
        if customer:
            log.info(
                "customer_resolved_by_phone",
                customer_id=customer.id,
                phone=message.customer_phone,
            )

    # ── Step 3: Create new customer ──────────────────────────────────────────
    if customer is None:
        customer = await create_customer(
            db=db,
            email=message.customer_email,
            phone=message.customer_phone,
            name=message.customer_name,
        )
        log.info(
            "customer_created",
            customer_id=customer.id,
            email=message.customer_email,
            phone=message.customer_phone,
        )

    # ── Enrich existing record with new info ─────────────────────────────────
    updates = {}

    # Link phone if we found customer by email but phone was unknown
    if message.customer_phone and not customer.phone:
        updates["phone"] = message.customer_phone

    # Link email if we found customer by phone but email was unknown
    if message.customer_email and not customer.email:
        updates["email"] = message.customer_email.lower().strip()

    # Update name if it was missing
    if message.customer_name and not customer.name:
        updates["name"] = message.customer_name

    if updates:
        await update_customer(db, customer.id, **updates)
        for key, val in updates.items():
            setattr(customer, key, val)  # keep in-memory object current
        log.info("customer_enriched", customer_id=customer.id, updates=updates)

    return customer
