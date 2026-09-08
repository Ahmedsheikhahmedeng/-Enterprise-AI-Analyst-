"""Pydantic schemas for embedding API requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentChunkEmbeddingResponse(BaseModel):
    """API representation of a single persisted document chunk embedding metadata record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    model: str
    version: str
    dimensions: int
    normalization: str
    embedding_input_hash: str
    token_count: int
    status: str
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentEmbeddingSummaryResponse(BaseModel):
    """Aggregated status and observability metrics of embeddings for a document."""

    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    model: str
    version: str
    dimensions: int
    normalization: str
    total_embeddings: int
    completed_count: int
    failed_count: int
    total_tokens: int
    latency_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    estimated_cost: float | None = None


class DocumentEmbeddingTriggerRequest(BaseModel):
    """Request payload to trigger embedding generation for a document's chunks."""

    force: bool = Field(
        default=False,
        description="If True, existing embeddings will be deleted and regenerated.",
    )
    sync: bool = Field(
        default=False,
        description="If True, executes synchronously and waits for completion.",
    )


class DocumentChunkEmbeddingListResponse(BaseModel):
    """Paginated list of document chunk embedding records."""

    items: list[DocumentChunkEmbeddingResponse]
    total: int
    skip: int
    limit: int
