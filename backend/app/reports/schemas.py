"""Pydantic schemas for Report API request payloads and structured responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateReportFromAnalysisRequest(BaseModel):
    """Payload to synthesize and persist an enterprise report from an analysis run."""

    analysis_run_id: UUID = Field(
        ..., description="Identifier of the completed AI Analyst AnalysisRun"
    )
    title: str = Field(
        ..., min_length=2, max_length=255, description="Human-readable business title"
    )
    subtitle: str | None = Field(
        None, max_length=255, description="Optional secondary title or brief theme"
    )
    template: str = Field(
        "executive", description="Report layout style: 'executive', 'detailed', 'technical'"
    )


class ReportListItemResponse(BaseModel):
    """Summarized report item for list views."""

    report_id: UUID
    organization_id: UUID
    title: str
    status: str
    current_version: int
    created_at: datetime
    published_at: datetime | None = None


class ReportListResponse(BaseModel):
    """Paginated collection of reports."""

    items: list[ReportListItemResponse]
    total: int
    page: int
    page_size: int


class ReportResponse(BaseModel):
    """Detailed response containing report metadata and the canonical structured document."""

    report_id: UUID
    organization_id: UUID
    title: str
    subtitle: str | None = None
    status: str
    version: int
    content_hash: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None
    document: dict[str, Any]
