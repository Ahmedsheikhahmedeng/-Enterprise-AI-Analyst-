"""Pydantic schemas for background jobs API and serialization."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobType(StrEnum):
    """Supported background job types."""

    DOCUMENT_INGESTION = "document_ingestion"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    VECTOR_INDEXING = "vector_indexing"
    EVALUATION = "evaluation"
    REPORT_EXPORT = "report_export"
    AGENT_EXECUTION = "agent_execution"
    DATA_SOURCE_SYNC = "data_source_sync"
    DATASET_INGESTION = "dataset_ingestion"


class JobStatus(StrEnum):
    """Explicit job execution lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class JobPriority(StrEnum):
    """Job scheduling priority."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class JobCreateRequest(BaseModel):
    """Request model to enqueue a new background job."""

    model_config = ConfigDict(extra="forbid")

    job_type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: JobPriority = Field(default=JobPriority.NORMAL)
    idempotency_key: str | None = Field(default=None, max_length=255)
    max_attempts: int | None = Field(default=None, ge=1, le=10)


class JobResponse(BaseModel):
    """Response model representing a job's details and status."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    job_id: uuid.UUID = Field(validation_alias="id")
    organization_id: uuid.UUID
    created_by: uuid.UUID | None = None
    job_type: str
    status: str
    priority: str
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    attempt: int
    max_attempts: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    next_retry_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    idempotency_key: str | None = None
    worker_id: str | None = None
    progress: float | None = 0.0
    progress_message: str | None = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    items: list[JobResponse]
    total: int
    page: int
    page_size: int
    pages: int


class JobCancelRequest(BaseModel):
    """Request body for cancelling a job."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default="Cancelled by user", max_length=255)


class JobRetryRequest(BaseModel):
    """Request body for retrying a failed/dead_letter job."""

    model_config = ConfigDict(extra="forbid")

    force: bool = Field(default=False)


class JobHealthResponse(BaseModel):
    """Health and queue status report for the background worker subsystem."""

    status: str
    redis_reachable: bool
    queue_depths: dict[str, int]
    active_workers: int
    stuck_jobs: int
