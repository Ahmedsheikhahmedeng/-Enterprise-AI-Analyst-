"""Test fixtures for compliance and security governance test suite."""

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
    """Provide isolated transactional database session for compliance tests."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        yield session
        await session.rollback()

    await dispose_database_engine(engine)
