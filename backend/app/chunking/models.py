"""Domain models and data contracts for the chunking subsystem."""

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkType(StrEnum):
    """Canonical chunk types supported by the chunking subsystem."""

    TEXT = "text"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST = "list"
    TABLE = "table"
    COMPOSITE = "composite"
    PARENT = "parent"


class SourceLocator(BaseModel):
    """Precise structural and physical source locator for a chunk."""

    model_config = ConfigDict(extra="ignore")

    document_id: uuid.UUID
    page_number: int | None = None
    section_title: str | None = None
    block_id: str | None = None
    table_id: str | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None


class IntermediateChunk(BaseModel):
    """In-memory chunk representation produced by chunking strategies before persistence."""

    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    document_id: uuid.UUID
    organization_id: uuid.UUID
    parent_chunk_id: uuid.UUID | None = None
    chunk_index: int
    chunk_type: ChunkType
    content: str
    heading_context: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    page_number: int | None = None
    section: str | None = None
    source_locator: dict[str, Any] = Field(default_factory=dict)
    token_count: int = 0
    character_count: int = 0
    content_hash: str = ""
    chunker_version: str = "1.0.0"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkQualitySummary(BaseModel):
    """Quality and distribution metrics for a chunked document."""

    model_config = ConfigDict(extra="ignore")

    document_id: uuid.UUID
    organization_id: uuid.UUID
    chunker_version: str
    total_chunks: int = 0
    parent_chunks: int = 0
    child_chunks: int = 0
    text_chunks: int = 0
    table_chunks: int = 0
    list_chunks: int = 0
    composite_chunks: int = 0
    other_chunks: int = 0
    min_tokens: int = 0
    max_tokens: int = 0
    mean_tokens: float = 0.0
    median_tokens: float = 0.0
    oversized_chunks: int = 0
    empty_chunks: int = 0
    duplicate_ratio: float = 0.0
    pages_covered: list[int] = Field(default_factory=list)
    sections_covered: list[str] = Field(default_factory=list)
