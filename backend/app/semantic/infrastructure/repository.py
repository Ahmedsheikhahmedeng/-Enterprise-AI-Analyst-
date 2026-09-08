"""Repository providing tenant-isolated database access for Semantic Catalog objects."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.semantic import (
    BusinessTerm,
    BusinessTermVersion,
    SemanticColumnMapping,
    SemanticConflict,
    SemanticDimension,
    SemanticEntity,
    SemanticMetric,
    SemanticRelationship,
)
from app.semantic.application.normalizer import SemanticTextNormalizer
from app.semantic.domain.enums import ConflictSeverity, SemanticStatus
from app.semantic.domain.errors import (
    SemanticObjectNotFoundError,
)


class SemanticRepository:
    """Encapsulates transactional CRUD operations over all semantic catalog entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------------------------
    # Business Terms & Versions
    # -------------------------------------------------------------------------

    async def create_term(
        self,
        organization_id: uuid.UUID,
        name: str,
        definition: str,
        description: str | None = None,
        category: str | None = None,
        owner: str | None = None,
        steward: str | None = None,
        created_by: uuid.UUID | None = None,
        status: SemanticStatus = SemanticStatus.DRAFT,
    ) -> BusinessTerm:
        """Create a new business term with initial version 1."""
        norm_name = SemanticTextNormalizer.normalize(name)
        term_id = uuid.uuid4()
        now = datetime.now(UTC)

        term = BusinessTerm(
            id=term_id,
            organization_id=organization_id,
            name=name,
            normalized_name=norm_name,
            description=description,
            definition=definition,
            category=category,
            owner=owner,
            steward=steward,
            status=status.value,
            version=1,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(term)

        # Snapshot initial version
        version_snap = BusinessTermVersion(
            id=uuid.uuid4(),
            organization_id=organization_id,
            term_id=term_id,
            version=1,
            definition=definition,
            description=description,
            created_by=created_by,
            created_at=now,
        )
        self.session.add(version_snap)
        await self.session.flush()
        return term

    async def update_term(
        self,
        term_id: uuid.UUID,
        organization_id: uuid.UUID,
        definition: str | None = None,
        description: str | None = None,
        category: str | None = None,
        owner: str | None = None,
        steward: str | None = None,
        updated_by: uuid.UUID | None = None,
    ) -> BusinessTerm:
        """Update term and record immutable version if definition changed."""
        term = await self.get_term(term_id, organization_id)
        if not term:
            raise SemanticObjectNotFoundError("term", term_id)

        now = datetime.now(UTC)
        definition_changed = definition is not None and definition != term.definition

        if definition_changed and definition is not None:
            term.version += 1
            term.definition = definition
            version_snap = BusinessTermVersion(
                id=uuid.uuid4(),
                organization_id=organization_id,
                term_id=term.id,
                version=term.version,
                definition=definition,
                description=description or term.description,
                created_by=updated_by,
                created_at=now,
            )
            self.session.add(version_snap)

        if description is not None:
            term.description = description
        if category is not None:
            term.category = category
        if owner is not None:
            term.owner = owner
        if steward is not None:
            term.steward = steward

        term.updated_at = now
        await self.session.flush()
        return term

    async def get_term(self, term_id: uuid.UUID, organization_id: uuid.UUID) -> BusinessTerm | None:
        stmt = (
            select(BusinessTerm)
            .where(
                BusinessTerm.id == term_id,
                BusinessTerm.organization_id == organization_id,
            )
            .options(selectinload(BusinessTerm.versions))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_terms(
        self,
        organization_id: uuid.UUID,
        status: SemanticStatus | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[BusinessTerm]:
        stmt = select(BusinessTerm).where(BusinessTerm.organization_id == organization_id)
        if status:
            stmt = stmt.where(BusinessTerm.status == status.value)
        if category:
            stmt = stmt.where(BusinessTerm.category == category)
        stmt = stmt.order_by(BusinessTerm.name).offset(offset).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Semantic Metrics
    # -------------------------------------------------------------------------

    async def create_metric(
        self,
        organization_id: uuid.UUID,
        name: str,
        definition: str,
        formula: str,
        aggregation: str,
        display_name: str | None = None,
        description: str | None = None,
        grain: str | None = None,
        filters: list[str] | None = None,
        unit: str | None = None,
        dataset_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
        status: SemanticStatus = SemanticStatus.DRAFT,
    ) -> SemanticMetric:
        norm_name = SemanticTextNormalizer.normalize(name)
        now = datetime.now(UTC)
        metric = SemanticMetric(
            id=uuid.uuid4(),
            organization_id=organization_id,
            name=name,
            normalized_name=norm_name,
            display_name=display_name,
            description=description,
            definition=definition,
            formula=formula,
            aggregation=aggregation.upper(),
            grain=grain,
            filters=filters or [],
            unit=unit,
            dataset_id=dataset_id,
            status=status.value,
            version=1,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(metric)
        await self.session.flush()
        return metric

    async def get_metric(
        self, metric_id: uuid.UUID, organization_id: uuid.UUID
    ) -> SemanticMetric | None:
        stmt = (
            select(SemanticMetric)
            .where(
                SemanticMetric.id == metric_id,
                SemanticMetric.organization_id == organization_id,
            )
            .options(selectinload(SemanticMetric.dataset))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_metrics(
        self,
        organization_id: uuid.UUID,
        status: SemanticStatus | None = None,
        dataset_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[SemanticMetric]:
        stmt = select(SemanticMetric).where(SemanticMetric.organization_id == organization_id)
        if status:
            stmt = stmt.where(SemanticMetric.status == status.value)
        if dataset_id:
            stmt = stmt.where(SemanticMetric.dataset_id == dataset_id)
        stmt = stmt.order_by(SemanticMetric.name).offset(offset).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Semantic Dimensions
    # -------------------------------------------------------------------------

    async def create_dimension(
        self,
        organization_id: uuid.UUID,
        dataset_id: uuid.UUID,
        column_id: uuid.UUID,
        name: str,
        data_type: str,
        description: str | None = None,
        hierarchy: list[str] | None = None,
        created_by: uuid.UUID | None = None,
        status: SemanticStatus = SemanticStatus.DRAFT,
    ) -> SemanticDimension:
        norm_name = SemanticTextNormalizer.normalize(name)
        now = datetime.now(UTC)
        dim = SemanticDimension(
            id=uuid.uuid4(),
            organization_id=organization_id,
            dataset_id=dataset_id,
            column_id=column_id,
            name=name,
            normalized_name=norm_name,
            description=description,
            data_type=data_type,
            hierarchy=hierarchy or [],
            status=status.value,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(dim)
        await self.session.flush()
        return dim

    async def get_dimension(
        self, dimension_id: uuid.UUID, organization_id: uuid.UUID
    ) -> SemanticDimension | None:
        stmt = (
            select(SemanticDimension)
            .where(
                SemanticDimension.id == dimension_id,
                SemanticDimension.organization_id == organization_id,
            )
            .options(
                selectinload(SemanticDimension.dataset),
                selectinload(SemanticDimension.column),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_dimensions(
        self,
        organization_id: uuid.UUID,
        dataset_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[SemanticDimension]:
        stmt = select(SemanticDimension).where(SemanticDimension.organization_id == organization_id)
        if dataset_id:
            stmt = stmt.where(SemanticDimension.dataset_id == dataset_id)
        stmt = stmt.order_by(SemanticDimension.name).offset(offset).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Semantic Entities & Relationships
    # -------------------------------------------------------------------------

    async def create_entity(
        self,
        organization_id: uuid.UUID,
        dataset_id: uuid.UUID,
        name: str,
        primary_key: str,
        description: str | None = None,
        display_name_column: str | None = None,
        created_by: uuid.UUID | None = None,
        status: SemanticStatus = SemanticStatus.DRAFT,
    ) -> SemanticEntity:
        norm_name = SemanticTextNormalizer.normalize(name)
        now = datetime.now(UTC)
        entity = SemanticEntity(
            id=uuid.uuid4(),
            organization_id=organization_id,
            dataset_id=dataset_id,
            name=name,
            normalized_name=norm_name,
            primary_key=primary_key,
            display_name_column=display_name_column,
            description=description,
            status=status.value,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_entity(
        self, entity_id: uuid.UUID, organization_id: uuid.UUID
    ) -> SemanticEntity | None:
        stmt = (
            select(SemanticEntity)
            .where(
                SemanticEntity.id == entity_id,
                SemanticEntity.organization_id == organization_id,
            )
            .options(selectinload(SemanticEntity.dataset))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_entities(
        self,
        organization_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[SemanticEntity]:
        stmt = (
            select(SemanticEntity)
            .where(SemanticEntity.organization_id == organization_id)
            .order_by(SemanticEntity.name)
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_relationship(
        self,
        organization_id: uuid.UUID,
        name: str,
        from_entity_id: uuid.UUID,
        to_entity_id: uuid.UUID,
        relationship_type: str,
        from_column: str,
        to_column: str,
        created_by: uuid.UUID | None = None,
        status: SemanticStatus = SemanticStatus.DRAFT,
    ) -> SemanticRelationship:
        now = datetime.now(UTC)
        rel = SemanticRelationship(
            id=uuid.uuid4(),
            organization_id=organization_id,
            name=name,
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relationship_type=relationship_type,
            from_column=from_column,
            to_column=to_column,
            status=status.value,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(rel)
        await self.session.flush()
        return rel

    async def list_relationships(
        self,
        organization_id: uuid.UUID,
        entity_id: uuid.UUID | None = None,
    ) -> list[SemanticRelationship]:
        stmt = select(SemanticRelationship).where(
            SemanticRelationship.organization_id == organization_id
        )
        if entity_id:
            stmt = stmt.where(
                (SemanticRelationship.from_entity_id == entity_id)
                | (SemanticRelationship.to_entity_id == entity_id)
            )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Column Mappings & Verification
    # -------------------------------------------------------------------------

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
        now = datetime.now(UTC)
        mapping = SemanticColumnMapping(
            id=uuid.uuid4(),
            organization_id=organization_id,
            semantic_object_type=semantic_object_type,
            semantic_object_id=semantic_object_id,
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
            column_id=column_id,
            mapping_type=mapping_type,
            confidence=confidence,
            is_verified=is_verified,
            verified_by=verified_by if is_verified else None,
            verified_at=now if is_verified else None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def verify_mapping(
        self,
        mapping_id: uuid.UUID,
        organization_id: uuid.UUID,
        verified_by: uuid.UUID,
    ) -> SemanticColumnMapping:
        stmt = select(SemanticColumnMapping).where(
            SemanticColumnMapping.id == mapping_id,
            SemanticColumnMapping.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        mapping = res.scalars().first()
        if not mapping:
            raise SemanticObjectNotFoundError("column_mapping", mapping_id)

        mapping.is_verified = True
        mapping.verified_by = verified_by
        mapping.verified_at = datetime.now(UTC)
        mapping.updated_at = datetime.now(UTC)
        await self.session.flush()
        return mapping

    async def list_mappings_for_object(
        self,
        organization_id: uuid.UUID,
        semantic_object_type: str,
        semantic_object_id: uuid.UUID,
    ) -> list[SemanticColumnMapping]:
        stmt = (
            select(SemanticColumnMapping)
            .where(
                SemanticColumnMapping.organization_id == organization_id,
                SemanticColumnMapping.semantic_object_type == semantic_object_type,
                SemanticColumnMapping.semantic_object_id == semantic_object_id,
            )
            .options(
                selectinload(SemanticColumnMapping.column),
                selectinload(SemanticColumnMapping.dataset),
            )
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Publishing State Machine
    # -------------------------------------------------------------------------

    async def publish_object(
        self,
        object_type: str,
        object_id: uuid.UUID,
        organization_id: uuid.UUID,
        target_status: SemanticStatus = SemanticStatus.PUBLISHED,
    ) -> Any:
        """Advance a semantic concept through the publishing lifecycle."""
        obj: Any = None
        if object_type == "term":
            obj = await self.get_term(object_id, organization_id)
        elif object_type == "metric":
            obj = await self.get_metric(object_id, organization_id)
        elif object_type == "dimension":
            obj = await self.get_dimension(object_id, organization_id)
        elif object_type == "entity":
            obj = await self.get_entity(object_id, organization_id)
        else:
            raise SemanticObjectNotFoundError(object_type, object_id)

        if not obj:
            raise SemanticObjectNotFoundError(object_type, object_id)

        obj.status = target_status.value
        obj.updated_at = datetime.now(UTC)
        await self.session.flush()
        return obj

    # -------------------------------------------------------------------------
    # Conflicts
    # -------------------------------------------------------------------------

    async def create_conflict(
        self,
        organization_id: uuid.UUID,
        object_type: str,
        object_ids: list[str],
        reason: str,
        severity: ConflictSeverity = ConflictSeverity.MEDIUM,
    ) -> SemanticConflict:
        conflict = SemanticConflict(
            id=uuid.uuid4(),
            organization_id=organization_id,
            object_type=object_type,
            object_ids=object_ids,
            severity=severity.value,
            reason=reason,
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        self.session.add(conflict)
        await self.session.flush()
        return conflict

    async def list_conflicts(
        self,
        organization_id: uuid.UUID,
        unresolved_only: bool = True,
    ) -> list[SemanticConflict]:
        stmt = select(SemanticConflict).where(SemanticConflict.organization_id == organization_id)
        if unresolved_only:
            stmt = stmt.where(SemanticConflict.is_resolved.is_(False))
        stmt = stmt.order_by(desc(SemanticConflict.created_at))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
