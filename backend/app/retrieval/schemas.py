"""Pydantic schemas for dense retrieval API requests and responses."""

import unicodedata
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.chunking.models import ChunkType
from app.core.config import get_settings

_settings = get_settings()


class DenseRetrievalRequest(BaseModel):
    """Request payload for semantic dense retrieval."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        description="Natural language query string.",
        min_length=_settings.RETRIEVAL_MIN_QUERY_CHARACTERS,
        max_length=_settings.RETRIEVAL_MAX_QUERY_CHARACTERS,
    )
    top_k: int = Field(
        default=_settings.RETRIEVAL_DEFAULT_TOP_K,
        ge=1,
        le=_settings.RETRIEVAL_MAX_TOP_K,
        description="Number of most similar chunks to retrieve.",
    )
    document_id: UUID | None = Field(
        default=None,
        description="Optional filter to restrict retrieval to a single document.",
    )
    chunk_type: str | None = Field(
        default=None,
        description="Optional filter by chunk structure type (e.g. text, table, paragraph).",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="Optional filter to restrict retrieval to chunks on a specific page.",
    )
    section: str | None = Field(
        default=None,
        description="Optional filter for chunks under a specific section heading.",
    )
    score_threshold: float | None = Field(
        default=None,
        description="Optional minimum vector similarity score threshold for candidate chunks.",
    )
    include_parent: bool = Field(
        default=_settings.RETRIEVAL_PARENT_CONTEXT_ENABLED,
        description="Whether to hydrate and include parent chunk context for child chunks.",
    )

    @field_validator("query")
    @classmethod
    def validate_and_normalize_query(cls, v: str) -> str:
        cleaned = unicodedata.normalize("NFC", v).strip()
        min_chars = _settings.RETRIEVAL_MIN_QUERY_CHARACTERS
        max_chars = _settings.RETRIEVAL_MAX_QUERY_CHARACTERS
        if len(cleaned) < min_chars:
            raise ValueError(f"Query must contain at least {min_chars} non-whitespace characters.")
        if len(cleaned) > max_chars:
            raise ValueError(f"Query exceeds maximum length of {max_chars} characters.")
        return cleaned

    @field_validator("chunk_type")
    @classmethod
    def validate_chunk_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid_types = {ct.value for ct in ChunkType}
        v_clean = v.strip().lower()
        if v_clean not in valid_types:
            raise ValueError(
                f"Invalid chunk_type '{v}'. Supported chunk types: {sorted(valid_types)}"
            )
        return v_clean


class RetrievedChunkResponse(BaseModel):
    """Pydantic model representing a single retrieved document chunk in API responses."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    document_id: UUID
    score: float = Field(
        ...,
        description="Raw vector similarity/distance score preserved from vector store engine.",
    )
    text: str
    chunk_index: int
    chunk_type: str
    token_count: int
    character_count: int
    page_number: int | None = None
    page_end: int | None = None
    section: str | None = None
    heading_hierarchy: list[str] = Field(default_factory=list)
    parent_chunk_id: UUID | None = None
    parent_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalLatencyBreakdown(BaseModel):
    """Latency metrics breakdown in milliseconds across retrieval pipeline phases."""

    embedding_ms: float
    vector_search_ms: float
    hydration_ms: float
    total_ms: float


class RetrievalDiagnosticsResponse(BaseModel):
    """Execution metadata and performance diagnostics for the retrieval request."""

    collection_name: str
    embedding_provider: str
    embedding_model: str
    dimensions: int
    query_character_count: int
    query_token_count: int
    total_candidates_found: int
    returned_chunks_count: int
    score_threshold: float | None = None
    latency: RetrievalLatencyBreakdown


class DenseRetrievalResponse(BaseModel):
    """Standardized top-level response container for dense retrieval operations."""

    query: str
    total_results: int
    results: list[RetrievedChunkResponse]
    diagnostics: RetrievalDiagnosticsResponse


class HybridRetrievalRequest(BaseModel):
    """Request payload for hybrid dense + sparse BM25 retrieval with RRF."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        description="Natural language or keyword search query.",
        min_length=_settings.RETRIEVAL_MIN_QUERY_CHARACTERS,
        max_length=_settings.RETRIEVAL_MAX_QUERY_CHARACTERS,
    )
    top_k: int = Field(
        default=_settings.HYBRID_DEFAULT_TOP_K,
        ge=1,
        le=_settings.HYBRID_MAX_TOP_K,
        description="Number of final fused chunks to retrieve.",
    )
    dense_candidate_k: int = Field(
        default=_settings.HYBRID_DENSE_CANDIDATE_K,
        ge=1,
        le=200,
        description="Candidate pool size retrieved from dense vector search.",
    )
    sparse_candidate_k: int = Field(
        default=_settings.HYBRID_SPARSE_CANDIDATE_K,
        ge=1,
        le=200,
        description="Candidate pool size retrieved from sparse BM25 search.",
    )
    rrf_k: int = Field(
        default=_settings.HYBRID_RRF_K,
        ge=1,
        le=200,
        description="Smoothing constant k for Reciprocal Rank Fusion formula: 1 / (k + rank).",
    )
    document_id: UUID | None = Field(
        default=None,
        description="Optional filter to restrict retrieval to a single document.",
    )
    chunk_type: str | None = Field(
        default=None,
        description="Optional filter by chunk structure type (e.g. text, table, paragraph).",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="Optional filter to restrict retrieval to chunks on a specific page.",
    )
    section: str | None = Field(
        default=None,
        description="Optional filter for chunks under a specific section heading.",
    )
    score_threshold: float | None = Field(
        default=None,
        description="Optional minimum vector similarity score threshold for dense candidates.",
    )
    rerank: bool = Field(
        default=_settings.RERANKING_ENABLED,
        description="Whether to execute cross-encoder reranking on the candidate pool.",
    )
    rerank_candidates: int = Field(
        default=_settings.RERANKER_MAX_CANDIDATES,
        ge=1,
        le=200,
        description="Candidate pool size sent to cross-encoder reranker prior to top-k truncation.",
    )
    include_parent: bool = Field(
        default=True,
        description="Whether to hydrate and include parent chunk context for child chunks.",
    )
    enable_query_understanding: bool | None = Field(
        default=None,
        description="Whether to run query understanding and search planning before retrieval.",
    )
    enable_query_rewrite: bool | None = Field(
        default=None,
        description="Whether to generate a search-oriented query rewrite.",
    )
    enable_query_expansion: bool | None = Field(
        default=None,
        description="Whether to generate domain synonyms and alternative queries.",
    )
    enable_query_decomposition: bool | None = Field(
        default=None,
        description="Whether to decompose compound/comparative queries into sub-queries.",
    )

    @field_validator("query")
    @classmethod
    def validate_and_normalize_query(cls, v: str) -> str:
        cleaned = unicodedata.normalize("NFC", v).strip()
        min_chars = _settings.RETRIEVAL_MIN_QUERY_CHARACTERS
        max_chars = _settings.RETRIEVAL_MAX_QUERY_CHARACTERS
        if len(cleaned) < min_chars:
            raise ValueError(f"Query must contain at least {min_chars} non-whitespace characters.")
        if len(cleaned) > max_chars:
            raise ValueError(f"Query exceeds maximum length of {max_chars} characters.")
        return cleaned

    @field_validator("chunk_type")
    @classmethod
    def validate_chunk_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid_types = {ct.value for ct in ChunkType}
        v_clean = v.strip().lower()
        if v_clean not in valid_types:
            raise ValueError(
                f"Invalid chunk_type '{v}'. Supported chunk types: {sorted(valid_types)}"
            )
        return v_clean


class HybridRetrievedChunkResponse(BaseModel):
    """Pydantic model representing a single fused document chunk in hybrid API responses."""

    model_config = ConfigDict(from_attributes=True)

    rank: int = Field(..., description="Final 1-indexed fused ranking order.")
    chunk_id: UUID
    document_id: UUID
    score: float = Field(
        ...,
        description="Primary retrieval score (rerank_score if reranked, else rrf_score).",
    )
    rrf_score: float = Field(..., description="Reciprocal Rank Fusion score: Σ 1 / (k + rank).")
    dense_score: float | None = Field(
        default=None,
        description="Raw similarity score from dense vector search if chunk matched dense.",
    )
    dense_rank: int | None = Field(
        default=None,
        description="1-based ordinal rank in dense vector candidate pool.",
    )
    sparse_score: float | None = Field(
        default=None,
        description="Raw BM25 lexical score from sparse search if chunk matched sparse.",
    )
    sparse_rank: int | None = Field(
        default=None,
        description="1-based ordinal rank in sparse BM25 candidate pool.",
    )
    rerank_score: float | None = Field(
        default=None,
        description="Relevance score from cross-encoder reranker if reranking was performed.",
    )
    rerank_rank: int | None = Field(
        default=None,
        description="1-based ordinal rank assigned by cross-encoder reranker.",
    )
    original_rank: int | None = Field(
        default=None,
        description="Original 1-based ordinal rank from RRF fusion prior to reranking.",
    )
    text: str
    chunk_index: int
    chunk_type: str
    token_count: int
    character_count: int
    page_number: int | None = None
    page_end: int | None = None
    section: str | None = None
    heading_hierarchy: list[str] = Field(default_factory=list)
    parent_chunk_id: UUID | None = None
    parent_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridLatencyBreakdown(BaseModel):
    """Latency metrics breakdown in milliseconds across hybrid retrieval phases."""

    dense_ms: float
    sparse_ms: float
    fusion_ms: float
    rerank_ms: float = 0.0
    hydration_ms: float
    total_ms: float


class HybridDiagnosticsResponse(BaseModel):
    """Execution metadata and performance diagnostics for hybrid search."""

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
    latency: HybridLatencyBreakdown


class HybridRetrievalResponse(BaseModel):
    """Standardized top-level response container for hybrid retrieval operations."""

    query: str
    retrieval_mode: str = Field(
        ...,
        description=(
            "Operational retrieval mode: 'hybrid', 'hybrid_reranked', "
            "'dense_fallback', or 'sparse_fallback'."
        ),
    )
    total_results: int
    results: list[HybridRetrievedChunkResponse]
    diagnostics: HybridDiagnosticsResponse
