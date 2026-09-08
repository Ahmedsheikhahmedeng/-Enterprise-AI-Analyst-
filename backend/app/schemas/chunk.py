"""Pydantic schemas for DocumentChunk API requests and responses."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentChunkResponse(BaseModel):
    """API representation of a single persisted document chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    organization_id: uuid.UUID
    parent_chunk_id: uuid.UUID | None = None
    chunk_index: int
    chunk_type: str | None = None
    content: str
    heading_context: str | None = None
    heading_path: list[str] | None = None
    page_number: int | None = None
    section: str | None = None
    source_locator: dict[str, Any] | None = None
    token_count: int
    character_count: int
    content_hash: str
    chunker_version: str
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    created_at: datetime


class DocumentChunkListResponse(BaseModel):
    """Paginated list of document chunks."""

    items: list[DocumentChunkResponse]
    total: int
    skip: int
    limit: int


class ChunkQualitySummaryResponse(BaseModel):
    """Quality and distribution metrics response for a document's chunks."""

    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    organization_id: uuid.UUID
    chunker_version: str
    total_chunks: int
    parent_chunks: int
    child_chunks: int
    text_chunks: int
    table_chunks: int
    list_chunks: int
    composite_chunks: int
    other_chunks: int
    min_tokens: int
    max_tokens: int
    mean_tokens: float
    median_tokens: float
    oversized_chunks: int
    empty_chunks: int
    duplicate_ratio: float
    pages_covered: list[int]
    sections_covered: list[str]
