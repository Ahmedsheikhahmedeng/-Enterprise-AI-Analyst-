"""Domain transfer models for vector store operations."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class SparseVector:
    """Represents a sparse vector with non-zero indices and their corresponding weights."""

    indices: list[int]
    values: list[float]


@dataclass
class VectorPoint:
    """Represents a single vector point prepared for ingestion into the vector store."""

    id: UUID
    vector: list[float]
    payload: dict[str, Any]
    sparse_vector: SparseVector | None = None

    @property
    def organization_id(self) -> str:
        return str(self.payload.get("organization_id", ""))

    @property
    def document_id(self) -> str:
        return str(self.payload.get("document_id", ""))

    @property
    def chunk_id(self) -> str:
        return str(self.payload.get("chunk_id", ""))


@dataclass
class VectorStoreStats:
    """Observability metadata describing the health and density of a vector collection."""

    collection_name: str
    points_count: int
    indexed_vectors_count: int
    vector_size: int
    distance: str
    status: str

    @property
    def vector_dimensions(self) -> int:
        return self.vector_size


@dataclass
class IndexingBatchResult:
    """Summary of batch vector upsert execution."""

    collection_name: str
    total_points: int
    successful_points: int
    failed_points: int
    failed_chunk_ids: list[UUID] = field(default_factory=list)
    batch_count: int = 0
    latency_ms: float = 0.0
    retry_count: int = 0
    status: str = "success"  # "success", "partial", "failure"


@dataclass
class VectorSearchResult:
    """Represents a single scored point returned from a vector search operation."""

    id: UUID
    score: float
    payload: dict[str, Any]
    vector: list[float] | None = None
    sparse_score: float | None = None
    sparse_vector: SparseVector | None = None

    @property
    def organization_id(self) -> str:
        return str(self.payload.get("organization_id", ""))

    @property
    def document_id(self) -> str:
        return str(self.payload.get("document_id", ""))

    @property
    def chunk_id(self) -> str:
        return str(self.payload.get("chunk_id", ""))
