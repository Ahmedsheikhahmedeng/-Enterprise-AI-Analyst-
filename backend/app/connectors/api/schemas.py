"""Pydantic schemas for Data Connectors and Data Sources API."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.connectors.domain.enums import ConnectorType, SyncStatus, SyncType


class DataSourceCreateRequest(BaseModel):
    """Payload to register a new external data source."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100, description="Display name of data source")
    type: ConnectorType = Field(..., description="Connector type (postgresql, csv, excel)")
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Connection configuration parameters (e.g. host, port, dbname, user, password or file_path)",
    )
    is_active: bool = Field(default=True, description="Whether data source is active")
    description: str | None = Field(
        default=None, max_length=500, description="Optional description"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("DataSource name cannot be blank or whitespace only")
        return clean

    @field_validator("configuration")
    @classmethod
    def validate_configuration(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("Configuration must be a key-value dictionary")
        return v


class DataSourceUpdateRequest(BaseModel):
    """Payload to update an existing data source."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    configuration: dict[str, Any] | None = Field(default=None)
    is_active: bool | None = Field(default=None)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("DataSource name cannot be blank or whitespace only")
            return clean
        return v


class DataSourceResponse(BaseModel):
    """Safe representation of a data source with credentials redacted."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    type: str
    connector_type: str
    status: str
    configuration: dict[str, Any]
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class DataSourceListResponse(BaseModel):
    """Paginated list of data sources."""

    items: list[DataSourceResponse]
    total: int


class DataSourceTestResponse(BaseModel):
    """Result of testing live connectivity to data source."""

    success: bool
    latency_ms: float
    message: str
    tested_at: datetime


class DataSourceQueryRequest(BaseModel):
    """Validated query execution request against a data source."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=20000, description="SQL query or command")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    timeout_ms: int = Field(default=5000, gt=0, le=60000, description="Timeout in milliseconds")
    max_rows: int = Field(default=1000, gt=0, le=10000, description="Maximum rows returned")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Query string cannot be empty or whitespace only")
        return clean


class DataSourceSyncRequest(BaseModel):
    """Request to initiate background data source synchronization."""

    model_config = ConfigDict(extra="forbid")

    sync_type: SyncType = Field(default=SyncType.FULL, description="Synchronization type (full)")
    options: dict[str, Any] = Field(default_factory=dict, description="Sync options")


class DataSourceSyncResponse(BaseModel):
    """Immediate response after initiating a synchronization run."""

    sync_id: uuid.UUID
    datasource_id: uuid.UUID
    status: SyncStatus
    sync_type: SyncType
    started_at: datetime | None = None
    message: str


class DataSourceHealthResponse(BaseModel):
    """Health check status and connectivity metrics for a data source."""

    datasource_id: uuid.UUID
    connector_type: str
    status: str
    healthy: bool
    last_checked_at: datetime
    metrics: dict[str, Any]
