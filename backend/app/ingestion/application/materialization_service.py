"""Materialization service managing dataset storage, columns, and zero-downtime version transitions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.domain.enums import DatasetStatus
from app.ingestion.domain.models import (
    ColumnDefinition,
    DataQualityReport,
    DatasetLineage,
    DatasetProfile,
    DatasetVersionModel,
)
from app.models.dataset import Dataset, DatasetColumn, DatasetVersion


class MaterializationService:
    """Coordinates atomic dataset materialization and zero-downtime version promotion."""

    async def get_or_create_dataset(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        name: str,
        source_type: str,
        source_datasource_id: uuid.UUID | None = None,
        description: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Dataset:
        """Find existing dataset for organization or create a new one in CREATED status."""
        stmt = select(Dataset).where(
            Dataset.organization_id == organization_id,
            Dataset.name == name,
        )
        res = await db_session.execute(stmt)
        dataset = res.scalars().first()

        if dataset is None:
            dataset = Dataset(
                organization_id=organization_id,
                name=name,
                description=description,
                source_type=source_type,
                source_datasource_id=source_datasource_id,
                status=DatasetStatus.CREATED.value,
                current_version=1,
                created_by=created_by,
            )
            db_session.add(dataset)
            await db_session.commit()
            await db_session.refresh(dataset)

        return dataset

    async def prepare_new_version(
        self,
        db_session: AsyncSession,
        dataset: Dataset,
        job_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
    ) -> DatasetVersion:
        """Create a new DatasetVersion in INGESTING status without touching active version."""
        # Find highest version number
        stmt = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset.id)
            .order_by(DatasetVersion.version.desc())
        )
        res = await db_session.execute(stmt)
        latest_version = res.scalars().first()

        new_version_num = (latest_version.version + 1) if latest_version else 1

        new_version = DatasetVersion(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            organization_id=dataset.organization_id,
            version=new_version_num,
            status=DatasetStatus.INGESTING.value,
            row_count=0,
            content_hash="",
            schema_hash="",
            job_id=job_id,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        db_session.add(new_version)
        await db_session.commit()
        await db_session.refresh(new_version)
        return new_version

    async def promote_version_success(
        self,
        db_session: AsyncSession,
        dataset: Dataset,
        version: DatasetVersion,
        columns: list[ColumnDefinition],
        profile: DatasetProfile,
        quality_report: DataQualityReport,
        lineage: DatasetLineage,
        storage_path: str,
        content_hash: str,
        schema_hash: str,
        row_count: int,
    ) -> DatasetVersionModel:
        """Promote the newly materialized version to READY and transition older versions to STALE."""
        # 1. Mark previous ready versions as STALE
        stale_stmt = (
            update(DatasetVersion)
            .where(
                DatasetVersion.dataset_id == dataset.id,
                DatasetVersion.id != version.id,
                DatasetVersion.status == DatasetStatus.READY.value,
            )
            .values(status=DatasetStatus.STALE.value)
        )
        await db_session.execute(stale_stmt)

        # 2. Promote current version to READY
        version.status = DatasetStatus.READY.value
        version.row_count = row_count
        version.content_hash = content_hash
        version.schema_hash = schema_hash
        version.storage_path = storage_path

        # 3. Synchronize DatasetColumn entities
        # Remove existing columns for clean schema update
        del_cols_stmt = select(DatasetColumn).where(DatasetColumn.dataset_id == dataset.id)
        existing_cols_res = await db_session.execute(del_cols_stmt)
        for col in existing_cols_res.scalars().all():
            await db_session.delete(col)

        for col_def in columns:
            col_prof = profile.columns.get(col_def.normalized_name)
            stats_dict = col_prof.model_dump() if col_prof else None
            new_col = DatasetColumn(
                dataset_id=dataset.id,
                name=col_def.name,
                normalized_name=col_def.normalized_name,
                original_name=col_def.original_name,
                data_type=col_def.data_type.value,
                nullable=col_def.nullable,
                ordinal_position=col_def.ordinal_position,
                pii_classification=col_def.pii_classification.value,
                stats=stats_dict,
            )
            db_session.add(new_col)

        # 4. Update parent Dataset entity
        dataset.status = DatasetStatus.READY.value
        dataset.current_version = version.version
        dataset.row_count = row_count
        dataset.quality_score = quality_report.score
        dataset.source_fingerprint = lineage.source_fingerprint
        dataset.schema_fingerprint = lineage.schema_fingerprint
        dataset.profile_data = profile.model_dump(mode="json")
        dataset.quality_report = quality_report.model_dump(mode="json")
        dataset.lineage_data = lineage.model_dump(mode="json")

        await db_session.commit()
        await db_session.refresh(version)

        return DatasetVersionModel(
            id=version.id or uuid.uuid4(),
            dataset_id=version.dataset_id,
            organization_id=version.organization_id,
            version=version.version,
            status=version.status,
            row_count=version.row_count,
            content_hash=version.content_hash,
            schema_hash=version.schema_hash,
            storage_path=version.storage_path,
            job_id=version.job_id,
            created_at=version.created_at or datetime.now(UTC),
        )

    async def mark_version_failure(
        self,
        db_session: AsyncSession,
        dataset: Dataset,
        version: DatasetVersion,
        error_message: str,
    ) -> None:
        """Mark ingesting version as FAILED. Older READY version remains active without downtime."""
        version.status = DatasetStatus.FAILED.value
        version.metadata_ = {"error": error_message}

        # If dataset had no previous ready version, mark dataset as FAILED
        check_ready_stmt = select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset.id,
            DatasetVersion.status == DatasetStatus.READY.value,
        )
        ready_res = await db_session.execute(check_ready_stmt)
        has_ready = ready_res.scalars().first() is not None

        if not has_ready:
            dataset.status = DatasetStatus.FAILED.value

        await db_session.commit()
