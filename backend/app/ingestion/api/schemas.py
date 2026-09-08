"""Pydantic schemas for Datasets and Materialization REST API."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.domain.enums import DeduplicationStrategy, IngestionMode


class DatasetColumnResponse(BaseModel):
    """Column definition response."""

    name: str
    normalized_name: str
    data_type: str
    nullable: bool
    ordinal_position: int
    pii_classification: str | None = None


class DatasetCreateRequest(BaseModel):
    """Request payload to register a new dataset."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    source_type: str = Field(..., min_length=1, max_length=50)
    source_datasource_id: uuid.UUID | None = None
    visibility: str = Field(default="internal", max_length=32)
    classification: str = Field(default="INTERNAL", max_length=32)
    ingestion_mode: IngestionMode = IngestionMode.STRUCTURED_ONLY


class DatasetUpdateRequest(BaseModel):
    """Request payload to update dataset properties."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=2000)
    visibility: str | None = Field(default=None, max_length=32)
    classification: str | None = Field(default=None, max_length=32)
    ingestion_mode: IngestionMode | None = None
    status: str | None = Field(default=None, max_length=50)


class DatasetResponse(BaseModel):
    """Detailed response representation of a Dataset."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    source_type: str
    status: str
    current_version: int
    row_count: int | None
    quality_score: float | None
    classification: str
    visibility: str
    source_datasource_id: uuid.UUID | None
    created_at: datetime
    columns: list[DatasetColumnResponse] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    """Paginated list of datasets."""

    datasets: list[DatasetResponse]
    total: int


class DatasetIngestRequest(BaseModel):
    """Request payload to initiate dataset ingestion and materialization."""

    model_config = ConfigDict(extra="forbid")

    batch_size: int = Field(default=1000, ge=10, le=10000)
    deduplication_strategy: DeduplicationStrategy = DeduplicationStrategy.EXACT_ROW_HASH
    deduplication_keys: list[str] = Field(default_factory=list)
    ingestion_mode: IngestionMode = IngestionMode.STRUCTURED_ONLY
    watermark_column: str | None = None
    last_watermark: str | None = None
    target_name: str | None = None
    run_async: bool = Field(default=False, description="Enqueue as background job via Worker")


class DatasetIngestResponse(BaseModel):
    """Response returned upon initiating or completing dataset ingestion."""

    dataset_id: uuid.UUID
    version: int
    status: str
    row_count: int = 0
    quality_score: float | None = None
    content_hash: str | None = None
    schema_hash: str | None = None
    job_id: uuid.UUID | None = None


class DatasetProfileResponse(BaseModel):
    """Response containing statistical dataset profile."""

    dataset_id: uuid.UUID
    name: str
    profile: dict[str, Any]


class DataQualityResponse(BaseModel):
    """Response containing data quality scorecard."""

    dataset_id: uuid.UUID
    name: str
    quality_score: float | None
    quality_report: dict[str, Any]


class DatasetVersionItem(BaseModel):
    """Summary of a specific dataset materialization version."""

    id: uuid.UUID
    version: int
    status: str
    row_count: int
    content_hash: str
    schema_hash: str
    created_at: datetime


class DatasetVersionsResponse(BaseModel):
    """List of all historical materialization versions."""

    dataset_id: uuid.UUID
    versions: list[DatasetVersionItem]


class DatasetLineageResponse(BaseModel):
    """Lineage and provenance metadata response."""

    dataset_id: uuid.UUID
    lineage: dict[str, Any]
