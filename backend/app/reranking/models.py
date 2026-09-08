"""Domain models for Cross-Encoder Reranking and execution diagnostics."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class RerankPair:
    """Represents a single query-candidate text pair for cross-encoder scoring."""

    query: str
    text: str
    chunk_id: UUID
    index: int


@dataclass
class RerankedCandidate:
    """Represents a candidate chunk scored and ranked by cross-encoder reranking."""

    chunk_id: UUID
    document_id: UUID
    organization_id: UUID
    rerank_score: float
    rerank_rank: int
    original_rrf_rank: int
    dense_score: float | None = None
    dense_rank: int | None = None
    sparse_score: float | None = None
    sparse_rank: int | None = None
    rrf_score: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RerankingLatency:
    """Latency breakdown in milliseconds for reranking phases."""

    inference_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class RerankingDiagnostics:
    """Observability metadata and runtime diagnostics for cross-encoder reranking."""

    provider: str
    model: str
    version: str
    device: str
    candidate_count: int
    reranked_count: int
    batch_count: int
    is_degraded: bool = False
    degradation_reason: str | None = None
    latency: RerankingLatency = field(default_factory=RerankingLatency)


@dataclass
class RerankingResult:
    """Complete response returned by CrossEncoderRerankingService."""

    candidates: list[RerankedCandidate]
    diagnostics: RerankingDiagnostics
