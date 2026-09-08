"""REST API endpoints for Datasets and Materialization Pipeline."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestAppException, NotFoundAppException
from app.db.postgres import get_db_session
from app.ingestion.api.schemas import (
    DataQualityResponse,
    DatasetColumnResponse,
    DatasetCreateRequest,
    DatasetIngestRequest,
    DatasetIngestResponse,
    DatasetLineageResponse,
    DatasetListResponse,
    DatasetProfileResponse,
    DatasetResponse,
    DatasetUpdateRequest,
    DatasetVersionItem,
    DatasetVersionsResponse,
)
from app.ingestion.application.ingestion_service import IngestionService
from app.ingestion.domain.enums import DatasetStatus
from app.ingestion.domain.errors import (
    DataQualityError,
    DatasetAlreadyExistsError,
    DatasetNotFoundError,
    DatasetNotReadyError,
    InvalidSchemaError,
    MaterializationError,
)
from app.ingestion.domain.models import IngestionConfig
from app.jobs.schemas import JobCreateRequest, JobType
from app.jobs.service import JobService
from app.models.audit import AuditLog
from app.models.dataset import Dataset, DatasetVersion
from app.rbac.catalog import (
    PERM_DATASET_CREATE,
    PERM_DATASET_DELETE,
    PERM_DATASET_INGEST,
    PERM_DATASET_PROFILE,
    PERM_DATASET_READ,
    PERM_DATASET_UPDATE,
    PERM_DATASET_VERSIONS,
)
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/datasets", tags=["Datasets & Materialization"])


def _map_error(exc: Exception) -> Exception:
    if isinstance(exc, DatasetNotFoundError):
        return NotFoundAppException(message=str(exc), code="DATASET_NOT_FOUND")
    if isinstance(exc, (DatasetNotReadyError, DatasetAlreadyExistsError, InvalidSchemaError)):
        return BadRequestAppException(message=str(exc), code="INVALID_DATASET_STATE")
    if isinstance(exc, (MaterializationError, DataQualityError)):
        return BadRequestAppException(message=str(exc), code="MATERIALIZATION_ERROR")
    return exc


def _serialize_dataset(dataset: Dataset) -> DatasetResponse:
    cols = [
        DatasetColumnResponse(
            name=c.name,
            normalized_name=c.normalized_name or c.name,
            data_type=c.data_type,
            nullable=c.nullable,
            ordinal_position=c.ordinal_position,
            pii_classification=c.pii_classification,
        )
        for c in (dataset.columns or [])
    ]
    return DatasetResponse(
        id=dataset.id,
        organization_id=dataset.organization_id,
        name=dataset.name,
        description=dataset.description,
        source_type=dataset.source_type,
        status=dataset.status,
        current_version=dataset.current_version,
        row_count=dataset.row_count,
        quality_score=dataset.quality_score,
        classification=dataset.classification,
        visibility=dataset.visibility,
        source_datasource_id=dataset.source_datasource_id,
        created_at=dataset.created_at,
        columns=cols,
    )


@router.post(
    "",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Dataset",
)
async def create_dataset(
    payload: DatasetCreateRequest,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_DATASET_CREATE))
    ],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatasetResponse:
    """Register a new Dataset for the current organization."""
    # Check uniqueness of name in org
    existing_stmt = select(Dataset).where(
        Dataset.organization_id == tenant_context.organization_id,
        Dataset.name == payload.name,
    )
    existing_res = await db_session.execute(existing_stmt)
    if existing_res.scalars().first():
        raise BadRequestAppException(
            message=f"Dataset with name '{payload.name}' already exists in this organization",
            code="DATASET_ALREADY_EXISTS",
        )

    dataset = Dataset(
        organization_id=tenant_context.organization_id,
        name=payload.name,
        description=payload.description,
        source_type=payload.source_type,
        source_datasource_id=payload.source_datasource_id,
        visibility=payload.visibility,
        classification=payload.classification,
        ingestion_mode=payload.ingestion_mode.value,
        status=DatasetStatus.CREATED.value,
        current_version=1,
        created_by=tenant_context.user_id,
    )
    db_session.add(dataset)
    await db_session.commit()
    await db_session.refresh(dataset)

    audit_entry = AuditLog(
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        action="DATASET_CREATED",
        resource_type="dataset",
        resource_id=str(dataset.id),
        metadata_={"name": dataset.name, "source_type": dataset.source_type},
    )
    db_session.add(audit_entry)
    await db_session.commit()

    return _serialize_dataset(dataset)


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List Datasets",
)
async def list_datasets(
    tenant_context: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASET_READ))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
) -> DatasetListResponse:
    """List datasets accessible to the current tenant."""
    query = (
        select(Dataset)
        .where(Dataset.organization_id == tenant_context.organization_id)
        .options(selectinload(Dataset.columns))
    )

    if status_filter:
        query = query.where(Dataset.status == status_filter.lower())

    count_query = select(func.count()).select_from(query.subquery())
    total_res = await db_session.execute(count_query)
    total = total_res.scalar_one()

    results_query = query.order_by(desc(Dataset.created_at)).offset(offset).limit(limit)
    res = await db_session.execute(results_query)
    datasets = res.scalars().all()

    return DatasetListResponse(
        datasets=[_serialize_dataset(d) for d in datasets],
        total=total,
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Get Dataset by ID",
)
async def get_dataset(
    dataset_id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASET_READ))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatasetResponse:
    """Retrieve detailed dataset representation."""
    stmt = (
        select(Dataset)
        .where(
            Dataset.id == dataset_id,
            Dataset.organization_id == tenant_context.organization_id,
        )
        .options(selectinload(Dataset.columns))
    )
    res = await db_session.execute(stmt)
    dataset = res.scalars().first()
    if not dataset:
        raise NotFoundAppException(
            message=f"Dataset {dataset_id} not found", code="DATASET_NOT_FOUND"
        )

    return _serialize_dataset(dataset)


@router.patch(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Update Dataset",
)
async def update_dataset(
    dataset_id: uuid.UUID,
    payload: DatasetUpdateRequest,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_DATASET_UPDATE))
    ],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatasetResponse:
    """Update dataset properties and classification."""
    stmt = (
        select(Dataset)
        .where(
            Dataset.id == dataset_id,
            Dataset.organization_id == tenant_context.organization_id,
        )
        .options(selectinload(Dataset.columns))
    )
    res = await db_session.execute(stmt)
    dataset = res.scalars().first()
    if not dataset:
        raise NotFoundAppException(
            message=f"Dataset {dataset_id} not found", code="DATASET_NOT_FOUND"
        )

    if payload.description is not None:
        dataset.description = payload.description
    if payload.visibility is not None:
        dataset.visibility = payload.visibility
    if payload.classification is not None:
        dataset.classification = payload.classification
    if payload.ingestion_mode is not None:
        dataset.ingestion_mode = payload.ingestion_mode.value
    if payload.status is not None:
        dataset.status = payload.status

    await db_session.commit()
    await db_session.refresh(dataset)

    return _serialize_dataset(dataset)


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete or Archive Dataset",
)
async def delete_dataset(
    dataset_id: uuid.UUID,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_DATASET_DELETE))
    ],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete dataset and associated columns and versions."""
    stmt = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.organization_id == tenant_context.organization_id,
    )
    res = await db_session.execute(stmt)
    dataset = res.scalars().first()
    if not dataset:
        raise NotFoundAppException(
            message=f"Dataset {dataset_id} not found", code="DATASET_NOT_FOUND"
        )

    await db_session.delete(dataset)
    await db_session.commit()

    audit_entry = AuditLog(
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        action="DATASET_ARCHIVED",
        resource_type="dataset",
        resource_id=str(dataset_id),
        metadata_={"status": "deleted"},
    )
    db_session.add(audit_entry)
    await db_session.commit()


@router.post(
    "/{dataset_id}/ingest",
    response_model=DatasetIngestResponse,
    summary="Trigger Dataset Ingestion & Materialization",
)
async def ingest_dataset_endpoint(
    dataset_id: uuid.UUID,
    payload: DatasetIngestRequest,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_DATASET_INGEST))
    ],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatasetIngestResponse:
    """Execute or enqueue dataset ingestion pipeline."""
    stmt = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.organization_id == tenant_context.organization_id,
    )
    res = await db_session.execute(stmt)
    dataset = res.scalars().first()
    if not dataset:
        raise NotFoundAppException(
            message=f"Dataset {dataset_id} not found", code="DATASET_NOT_FOUND"
        )

    config = IngestionConfig(
        batch_size=payload.batch_size,
        deduplication_strategy=payload.deduplication_strategy,
        deduplication_keys=payload.deduplication_keys,
        ingestion_mode=payload.ingestion_mode,
        watermark_column=payload.watermark_column,
        last_watermark=payload.last_watermark,
    )

    if payload.run_async:
        # Enqueue via Task 23 JobService
        job_service = JobService()
        job_req = JobCreateRequest(
            job_type=JobType.DATASET_INGESTION,
            payload={
                "dataset_id": str(dataset_id),
                "batch_size": payload.batch_size,
                "deduplication_strategy": payload.deduplication_strategy.value,
                "deduplication_keys": payload.deduplication_keys,
                "ingestion_mode": payload.ingestion_mode.value,
                "watermark_column": payload.watermark_column,
                "last_watermark": payload.last_watermark,
                "target_name": payload.target_name,
            },
        )
        job = await job_service.create_job(
            db=db_session,
            request=job_req,
            organization_id=tenant_context.organization_id,
            created_by=tenant_context.user_id,
        )
        return DatasetIngestResponse(
            dataset_id=dataset_id,
            version=dataset.current_version,
            status="queued",
            job_id=job.id,
        )

    # Synchronous materialization
    ingestion_service = IngestionService()
    try:
        mat_result = await ingestion_service.ingest_dataset(
            db_session=db_session,
            organization_id=tenant_context.organization_id,
            dataset_id=dataset_id,
            config=config,
            user_id=tenant_context.user_id,
            target_name=payload.target_name,
        )
        return DatasetIngestResponse(
            dataset_id=dataset_id,
            version=mat_result.version,
            status="completed",
            row_count=mat_result.row_count,
            quality_score=mat_result.quality_report.score,
            content_hash=mat_result.content_hash,
            schema_hash=mat_result.schema_hash,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/{dataset_id}/profile",
    response_model=DatasetProfileResponse,
    summary="Get Dataset Profile",
)
async def get_dataset_profile(
    dataset_id: uuid.UUID,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_DATASET_PROFILE))
    ],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatasetProfileResponse:
    """Retrieve statistical data profile."""
    stmt = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.organization_id == tenant_context.organization_id,
    )
    res = await db_session.execute(stmt)
    dataset = res.scalars().first()
    if not dataset:
        raise NotFoundAppException(
            message=f"Dataset {dataset_id} not found", code="DATASET_NOT_FOUND"
        )

    return DatasetProfileResponse(
        dataset_id=dataset.id,
        name=dataset.name,
        profile=dataset.profile_data or {},
    )


@router.get(
    "/{dataset_id}/quality",
    response_model=DataQualityResponse,
    summary="Get Data Quality Scorecard",
)
async def get_data_quality(
    dataset_id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASET_READ))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataQualityResponse:
    """Retrieve data quality report."""
    stmt = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.organization_id == tenant_context.organization_id,
    )
    res = await db_session.execute(stmt)
    dataset = res.scalars().first()
    if not dataset:
        raise NotFoundAppException(
            message=f"Dataset {dataset_id} not found", code="DATASET_NOT_FOUND"
        )

    return DataQualityResponse(
        dataset_id=dataset.id,
        name=dataset.name,
        quality_score=dataset.quality_score,
        quality_report=dataset.quality_report or {},
    )


@router.get(
    "/{dataset_id}/versions",
    response_model=DatasetVersionsResponse,
    summary="List Dataset Materialization Versions",
)
async def list_dataset_versions(
    dataset_id: uuid.UUID,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_DATASET_VERSIONS))
    ],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatasetVersionsResponse:
    """Retrieve all historical materialization snapshots for dataset."""
    stmt = (
        select(DatasetVersion)
        .where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.organization_id == tenant_context.organization_id,
        )
        .order_by(desc(DatasetVersion.version))
    )
    res = await db_session.execute(stmt)
    versions = res.scalars().all()

    items = [
        DatasetVersionItem(
            id=v.id,
            version=v.version,
            status=v.status,
            row_count=v.row_count,
            content_hash=v.content_hash,
            schema_hash=v.schema_hash,
            created_at=v.created_at,
        )
        for v in versions
    ]

    return DatasetVersionsResponse(
        dataset_id=dataset_id,
        versions=items,
    )


@router.get(
    "/{dataset_id}/lineage",
    response_model=DatasetLineageResponse,
    summary="Get Dataset Lineage and Provenance",
)
async def get_dataset_lineage(
    dataset_id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASET_READ))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatasetLineageResponse:
    """Retrieve lineage, fingerprints, and provenance."""
    stmt = select(Dataset).where(
        Dataset.id == dataset_id,
        Dataset.organization_id == tenant_context.organization_id,
    )
    res = await db_session.execute(stmt)
    dataset = res.scalars().first()
    if not dataset:
        raise NotFoundAppException(
            message=f"Dataset {dataset_id} not found", code="DATASET_NOT_FOUND"
        )

    return DatasetLineageResponse(
        dataset_id=dataset.id,
        lineage=dataset.lineage_data or {},
    )
