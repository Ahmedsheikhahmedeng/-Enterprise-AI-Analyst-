"""Domain models and DTOs for the embedding layer."""

from dataclasses import dataclass, field
from uuid import UUID

EmbeddingVector = list[float]


@dataclass
class EmbeddingItem:
    """Represents a single chunk or text undergoing embedding."""

    text: str
    embedding_input_hash: str
    token_count: int
    chunk_id: UUID | None = None
    vector: EmbeddingVector | None = None
    cached: bool = False
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.vector is not None and self.error is None


@dataclass
class EmbeddingUsageMetrics:
    """Observability and cost tracking metrics for an embedding operation."""

    provider: str
    model: str
    version: str
    dimensions: int
    batch_size: int
    input_count: int
    total_input_tokens: int
    latency_ms: float = 0.0
    retry_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    estimated_cost: float | None = None


@dataclass
class EmbeddingBatchResult:
    """Aggregated result of processing a batch of chunks/texts."""

    items: list[EmbeddingItem] = field(default_factory=list)
    metrics: EmbeddingUsageMetrics | None = None
    status: str = "success"  # "success", "partial", "failure"
    failed_count: int = 0
    success_count: int = 0

    @property
    def vectors(self) -> list[EmbeddingVector | None]:
        return [item.vector for item in self.items]
