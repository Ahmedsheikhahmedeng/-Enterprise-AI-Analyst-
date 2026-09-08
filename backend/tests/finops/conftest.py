"""Test fixtures for Enterprise FinOps and AI Cost Governance."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide isolated transactional database session for FinOps tests."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        yield session
        await session.rollback()

    await dispose_database_engine(engine)


@pytest.fixture
def test_org_id() -> uuid.UUID:
    """Primary tenant organization identifier."""
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def other_org_id() -> uuid.UUID:
    """Secondary tenant organization identifier for isolation testing."""
    return uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Test user identifier."""
    return uuid.UUID("11111111-1111-1111-1111-111111111111")
