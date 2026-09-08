"""Domain models for hybrid retrieval, Reciprocal Rank Fusion, and execution diagnostics."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.retrieval.models import RetrievedChunk


@dataclass
class FusedCandidate:
    """Represents a deduplicated chunk candidate scored via Reciprocal Rank Fusion."""

    chunk_id: UUID
    document_id: UUID
    organization_id: UUID
    rrf_score: float
    rank: int = 0
    dense_score: float | None = None
    dense_rank: int | None = None
    sparse_score: float | None = None
    sparse_rank: int | None = None
    rerank_score: float | None = None
    rerank_rank: int | None = None
    original_rrf_rank: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridRetrievedChunk(RetrievedChunk):
    """Extends RetrievedChunk with hybrid retrieval, RRF, and cross-encoder reranking metadata."""

    retrieval_mode: str = "hybrid"
    rrf_score: float = 0.0
    dense_score: float | None = None
    dense_rank: int | None = None
    sparse_score: float | None = None
    sparse_rank: int | None = None
    rerank_score: float | None = None
    rerank_rank: int | None = None
    original_rank: int | None = None


@dataclass
class HybridRetrievalLatency:
    """Latency breakdown in milliseconds for each phase of hybrid retrieval."""

    dense_ms: float = 0.0
    sparse_ms: float = 0.0
    fusion_ms: float = 0.0
    rerank_ms: float = 0.0
    hydration_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class HybridRetrievalDiagnostics:
    """Observability metadata and performance diagnostics for hybrid search."""

    collection_name: str
    dense_candidate_count: int
    sparse_candidate_count: int
    merged_candidate_count: int
    final_result_count: int
    rrf_k: int
    dense_candidate_k: int
    sparse_candidate_k: int
    final_top_k: int
    reranking_enabled: bool = False
    reranker_provider: str | None = None
    reranker_model: str | None = None
    reranker_version: str | None = None
    reranker_candidate_count: int = 0
    is_degraded: bool = False
    degradation_reason: str | None = None
    latency: HybridRetrievalLatency = field(default_factory=HybridRetrievalLatency)


@dataclass
class HybridRetrievalResult:
    """Complete domain response for a hybrid retrieval operation."""

    query: str
    retrieval_mode: str  # "hybrid", "dense_fallback", "sparse_fallback"
    chunks: list[HybridRetrievedChunk]
    diagnostics: HybridRetrievalDiagnostics

    @property
    def total_results(self) -> int:
        return len(self.chunks)
