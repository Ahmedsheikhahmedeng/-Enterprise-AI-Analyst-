"""Domain models for dataset ingestion, profiling, quality, and materialization."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.ingestion.domain.enums import (
    ColumnDataType,
    DataClassification,
    DeduplicationStrategy,
    IngestionMode,
    PIIClassification,
)


class ColumnDefinition(BaseModel):
    """Definition of a single column within a dataset schema."""

    name: str
    normalized_name: str
    original_name: str | None = None
    data_type: ColumnDataType = ColumnDataType.STRING
    nullable: bool = True
    ordinal_position: int = 0
    pii_classification: PIIClassification = PIIClassification.NONE
    description: str | None = None


class ColumnProfile(BaseModel):
    """Statistical profile of a single column."""

    name: str
    data_type: str
    total_count: int = 0
    null_count: int = 0
    null_ratio: float = 0.0
    distinct_count: int = 0

    # Numeric statistics
    min_value: float | None = None
    max_value: float | None = None
    mean_value: float | None = None
    median_value: float | None = None

    # Text statistics
    min_length: int | None = None
    max_length: int | None = None
    avg_length: float | None = None

    # Date / Time statistics
    min_date: str | None = None
    max_date: str | None = None

    # Classification
    pii_classification: PIIClassification = PIIClassification.NONE


class DatasetProfile(BaseModel):
    """Aggregated statistical profile of a dataset."""

    dataset_id: uuid.UUID
    organization_id: uuid.UUID
    row_count: int = 0
    column_count: int = 0
    columns: dict[str, ColumnProfile] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DataQualityReport(BaseModel):
    """Data quality scorecard for a dataset."""

    score: float = Field(ge=0.0, le=1.0)
    null_ratio: float = 0.0
    duplicate_ratio: float = 0.0
    invalid_ratio: float = 0.0
    schema_consistency: float = 1.0
    details: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DatasetLineage(BaseModel):
    """Data provenance and lineage tracker."""

    dataset_id: uuid.UUID
    source_datasource_id: uuid.UUID | None = None
    organization_id: uuid.UUID
    source_fingerprint: str | None = None
    schema_fingerprint: str | None = None
    content_fingerprint: str | None = None
    ingestion_job_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DatasetVersionModel(BaseModel):
    """Domain model of a materialized dataset version."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    organization_id: uuid.UUID
    version: int
    status: str
    row_count: int
    content_hash: str
    schema_hash: str
    storage_path: str | None = None
    job_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IngestionChunk(BaseModel):
    """Bounded tabular chunk processed in streaming batches."""

    chunk_index: int
    rows: list[dict[str, Any]]
    row_count: int
    byte_size: int = 0


class IngestionConfig(BaseModel):
    """Configuration options for a dataset ingestion run."""

    batch_size: int = Field(default=1000, ge=10, le=10000)
    deduplication_strategy: DeduplicationStrategy = DeduplicationStrategy.EXACT_ROW_HASH
    deduplication_keys: list[str] = Field(default_factory=list)
    ingestion_mode: IngestionMode = IngestionMode.STRUCTURED_ONLY
    watermark_column: str | None = None
    last_watermark: str | None = None
    max_rows: int = Field(default=1_000_000, ge=1, le=5_000_000)


class MaterializationResult(BaseModel):
    """Outcome of materializing a dataset version."""

    dataset_id: uuid.UUID
    version: int
    row_count: int
    content_hash: str
    schema_hash: str
    storage_path: str | None = None
    profile: DatasetProfile
    quality_report: DataQualityReport
    lineage: DatasetLineage
    classification: DataClassification = DataClassification.INTERNAL
