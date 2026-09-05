"""Base repository enforcing tenant-scoped database query isolation."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import CursorResult, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base


class TenantScopedRepository[ModelType: Base]:
    """Abstract base repository mandating tenant organization scope on all database operations.

    Ensures that every SELECT, INSERT, UPDATE, DELETE, and COUNT query includes:
    WHERE organization_id = :organization_id
    making it architecturally impossible to accidentally bypass tenant isolation.
    """

    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    async def get_by_id(
        self,
        session: AsyncSession,
        id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ModelType | None:
        """Fetch a single entity by ID strictly scoped to the tenant organization."""
        stmt = select(self.model).where(
            self.model.id == id,  # type: ignore[attr-defined]
            self.model.organization_id == organization_id,  # type: ignore[attr-defined]
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelType]:
        """List entities for organization, applying tenant filtering before pagination."""
        stmt = (
            select(self.model)
            .where(self.model.organization_id == organization_id)  # type: ignore[attr-defined]
            .order_by(self.model.created_at.desc())  # type: ignore[attr-defined]
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def count(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> int:
        """Count entities strictly within the tenant organization scope."""
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.organization_id == organization_id)  # type: ignore[attr-defined]
        )
        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def create(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        **kwargs: Any,
    ) -> ModelType:
        """Create and persist an entity, strictly binding it to the trusted organization_id."""
        # Force organization_id from the trusted context, discarding any untrusted payload org_id
        kwargs["organization_id"] = organization_id
        entity = self.model(**kwargs)
        session.add(entity)
        await session.flush()
        return entity

    async def update(
        self,
        session: AsyncSession,
        id: uuid.UUID,
        organization_id: uuid.UUID,
        **values: Any,
    ) -> ModelType | None:
        """Update an entity matching both ID and organization_id.

        Returns None if zero rows were affected (preventing cross-tenant mutation).
        """
        # Disallow tampering with the entity's organization_id
        values.pop("organization_id", None)

        stmt = (
            update(self.model)
            .where(
                self.model.id == id,  # type: ignore[attr-defined]
                self.model.organization_id == organization_id,  # type: ignore[attr-defined]
            )
            .values(**values)
        )
        result = await session.execute(stmt)
        rowcount = result.rowcount if isinstance(result, CursorResult) else 1
        if rowcount == 0:
            return None

        await session.flush()
        return await self.get_by_id(session, id=id, organization_id=organization_id)

    async def delete(
        self,
        session: AsyncSession,
        id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> bool:
        """Delete an entity matching both ID and organization_id.

        Returns False if zero rows were affected (preventing cross-tenant deletion).
        """
        stmt = delete(self.model).where(
            self.model.id == id,  # type: ignore[attr-defined]
            self.model.organization_id == organization_id,  # type: ignore[attr-defined]
        )
        result = await session.execute(stmt)
        return bool(result.rowcount > 0) if isinstance(result, CursorResult) else True
