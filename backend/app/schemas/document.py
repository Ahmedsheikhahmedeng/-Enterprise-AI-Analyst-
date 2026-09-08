"""Document response and query schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Document metadata response model."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: uuid.UUID = Field(..., description="Unique document identifier")
    name: str = Field(..., description="Document display name")
    original_filename: str = Field(..., description="Sanitized original upload filename")
    mime_type: str = Field(..., description="Declared or standard MIME content type")
    detected_mime_type: str | None = Field(
        None,
        description="MIME type detected from file signature",
    )
    file_size: int = Field(..., description="File size in bytes")
    sha256: str = Field(..., description="Hex-encoded SHA-256 integrity checksum")
    status: str = Field(
        ...,
        description="Document status (uploaded, processing, parsed, failed, deleted)",
    )
    failure_reason: str | None = Field(
        None,
        description="Safe failure explanation if parsing failed",
    )
    parser_name: str | None = Field(None, description="Parser engine name")
    parser_version: str | None = Field(None, description="Parser version")
    parsed_at: datetime | None = Field(None, description="Timestamp of successful parsing")
    page_count: int | None = Field(
        None,
        description="Page count (populated during ingestion)",
    )
    created_by: uuid.UUID | None = Field(
        None,
        description="Identifier of the user who uploaded the document",
    )
    created_at: datetime = Field(..., description="Timestamp of document creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")


class DocumentListResponse(BaseModel):
    """Paginated list of document metadata items."""

    model_config = ConfigDict(frozen=True)

    items: list[DocumentResponse] = Field(..., description="List of tenant-owned documents")
    total: int = Field(..., description="Total document count for tenant")
    skip: int = Field(..., description="Pagination offset applied")
    limit: int = Field(..., description="Pagination limit applied")
