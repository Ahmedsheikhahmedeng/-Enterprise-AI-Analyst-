"""Domain models representing schemas, queries, results, and provenance."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.connectors.domain.enums import ConnectorType, SyncStatus, SyncType


class ColumnSchema(BaseModel):
    """Schema descriptor for an individual column or field."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1, max_length=255)
    data_type: str = Field(..., min_length=1, max_length=100)
    nullable: bool = True
    primary_key: bool = False
    foreign_key: str | None = None
    description: str | None = None


class TableSchema(BaseModel):
    """Schema descriptor for a database table, view, or sheet."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1, max_length=255)
    schema_name: str | None = None
    columns: list[ColumnSchema] = Field(default_factory=list)
    primary_keys: list[str] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list)
    row_count_estimate: int | None = None
    description: str | None = None


class SchemaModel(BaseModel):
    """Normalized schema definition representing discovered structure across any connector."""

    model_config = ConfigDict(frozen=True)

    datasource_id: uuid.UUID
    organization_id: uuid.UUID
    connector_type: ConnectorType
    tables: list[TableSchema] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1


class QueryRequest(BaseModel):
    """Encapsulates a query execution request bounded by limits and tenant context."""

    model_config = ConfigDict(frozen=True)

    datasource_id: uuid.UUID
    organization_id: uuid.UUID
    query: str = Field(..., min_length=1, max_length=20000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=5000, ge=100, le=60000)
    max_rows: int = Field(default=1000, ge=1, le=10000)


class QueryResult(BaseModel):
    """Normalized tabular result returned from query execution."""

    model_config = ConfigDict(frozen=True)

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    datasource_id: uuid.UUID
    provenance: dict[str, Any] = Field(default_factory=dict)


class PreviewResult(BaseModel):
    """Safe, bounded sample preview of a data source table or file."""

    model_config = ConfigDict(frozen=True)

    datasource_id: uuid.UUID
    target_name: str | None = None
    columns: list[ColumnSchema]
    rows: list[dict[str, Any]]
    total_rows_estimate: int | None = None
    sample_size: int = 0


class ConnectionTestResult(BaseModel):
    """Outcome of a live connection health verification."""

    model_config = ConfigDict(frozen=True)

    success: bool
    latency_ms: float
    message: str
    server_version: str | None = None
    tested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SyncRunModel(BaseModel):
    """Snapshot representation of a data source synchronization run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    data_source_id: uuid.UUID
    sync_type: SyncType
    status: SyncStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    rows_synced: int = 0
    error_message: str | None = None
    meta_info: dict[str, Any] = Field(default_factory=dict)
