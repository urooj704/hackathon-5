"""
Shared pytest fixtures for all tests.

Uses an in-memory SQLite DB with the same ORM models for fast, isolated tests.
Note: pgvector is PostgreSQL-only, so vector search tests are skipped in SQLite mode.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.db.models import Base, Customer, PlanEnum


# ─── In-memory DB engine ──────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(db_engine) -> AsyncSession:
    """Provide an AsyncSession for each test, auto-rollback on teardown."""
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ─── Sample data fixtures ─────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def sample_customer(db: AsyncSession) -> Customer:
    from src.db.crud import create_customer

    customer = await create_customer(
        db,
        email="test@example.com",
        name="Test User",
        plan=PlanEnum.GROWTH,
    )
    await db.commit()
    return customer
