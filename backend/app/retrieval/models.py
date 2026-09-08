"""Domain models for dense retrieval results and execution diagnostics."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class RetrievedChunk:
    """Represents an enriched document chunk matched via dense vector retrieval."""

    chunk_id: UUID
    document_id: UUID
    organization_id: UUID
    score: float  # Raw similarity/distance score preserved from vector store
    text: str
    chunk_index: int
    chunk_type: str
    token_count: int
    character_count: int
    page_number: int | None = None
    page_end: int | None = None
    section: str | None = None
    heading_hierarchy: list[str] = field(default_factory=list)
    parent_chunk_id: UUID | None = None
    parent_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalDiagnostics:
    """Diagnostic and observability metrics for a retrieval execution."""

    collection_name: str
    embedding_provider: str
    embedding_model: str
    dimensions: int
    query_character_count: int
    query_token_count: int
    total_candidates_found: int
    returned_chunks_count: int
    score_threshold: float | None = None
    embedding_latency_ms: float = 0.0
    vector_search_latency_ms: float = 0.0
    hydration_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass
class DenseRetrievalResult:
    """Complete domain response for a dense retrieval request."""

    query: str
    chunks: list[RetrievedChunk]
    diagnostics: RetrievalDiagnostics
