"""Application service managing physical-to-semantic column bindings and verifications."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset, DatasetColumn
from app.models.semantic import SemanticColumnMapping
from app.semantic.domain.errors import (
    SemanticError,
)
from app.semantic.infrastructure.repository import SemanticRepository


class MappingService:
    """Manages bindings from physical dataset columns to semantic terms, metrics, and dimensions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SemanticRepository(session)

    async def create_mapping(
        self,
        organization_id: uuid.UUID,
        semantic_object_type: str,
        semantic_object_id: uuid.UUID,
        dataset_id: uuid.UUID,
        column_id: uuid.UUID,
        dataset_version_id: uuid.UUID | None = None,
        mapping_type: str = "DIRECT",
        confidence: float = 1.0,
        is_verified: bool = False,
        verified_by: uuid.UUID | None = None,
    ) -> SemanticColumnMapping:
        """Create mapping while strictly guaranteeing tenant boundaries."""
        # 1. Verify dataset belongs to tenant
        ds_stmt = select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.organization_id == organization_id,
        )
        ds = (await self.session.execute(ds_stmt)).scalars().first()
        if not ds:
            raise SemanticError(f"Target Dataset '{dataset_id}' not found for tenant.")

        # 2. Verify column exists on this dataset
        col_stmt = select(DatasetColumn).where(
            DatasetColumn.id == column_id,
            DatasetColumn.dataset_id == dataset_id,
        )
        col = (await self.session.execute(col_stmt)).scalars().first()
        if not col:
            raise SemanticError(f"Target Column '{column_id}' not found on dataset '{dataset_id}'.")

        # 3. Create mapping
        return await self.repo.create_mapping(
            organization_id=organization_id,
            semantic_object_type=semantic_object_type,
            semantic_object_id=semantic_object_id,
            dataset_id=dataset_id,
            column_id=column_id,
            dataset_version_id=dataset_version_id,
            mapping_type=mapping_type,
            confidence=confidence,
            is_verified=is_verified,
            verified_by=verified_by,
        )

    async def verify_mapping(
        self,
        mapping_id: uuid.UUID,
        organization_id: uuid.UUID,
        verified_by: uuid.UUID,
    ) -> SemanticColumnMapping:
        """Mark a semantic mapping as human-verified and authoritative."""
        return await self.repo.verify_mapping(
            mapping_id=mapping_id,
            organization_id=organization_id,
            verified_by=verified_by,
        )

    async def list_mappings(
        self,
        organization_id: uuid.UUID,
        semantic_object_type: str,
        semantic_object_id: uuid.UUID,
    ) -> list[SemanticColumnMapping]:
        return await self.repo.list_mappings_for_object(
            organization_id=organization_id,
            semantic_object_type=semantic_object_type,
            semantic_object_id=semantic_object_id,
        )
