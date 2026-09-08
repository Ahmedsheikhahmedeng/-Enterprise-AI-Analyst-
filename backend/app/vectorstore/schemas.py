"""Pydantic schemas for vector store operations and status reporting."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentIndexingResponse(BaseModel):
    """Response returned upon initiating or completing document vector indexing."""

    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    organization_id: UUID
    collection_name: str
    total_points: int
    indexed_points: int
    failed_points: int
    latency_ms: float = 0.0
    status: str


class DocumentIndexingStatusResponse(BaseModel):
    """Observability response describing indexing coverage of a document's chunks in Qdrant."""

    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    organization_id: UUID
    collection_name: str
    total_chunks: int
    indexed_chunks: int
    pending_chunks: int
    indexing_status: str = "vector_pending"
    is_indexed: bool
    indexed_at: datetime | None = None


class VectorStoreStatsResponse(BaseModel):
    """Collection size, dimension, and status metrics."""

    model_config = ConfigDict(from_attributes=True)

    collection_name: str
    points_count: int
    indexed_vectors_count: int
    vector_size: int
    distance: str
    status: str


class VectorStoreHealthResponse(BaseModel):
    """Overall vector store connectivity and collection listing."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    collections: list[str]
    url: str
    latency_ms: float = 0.0
