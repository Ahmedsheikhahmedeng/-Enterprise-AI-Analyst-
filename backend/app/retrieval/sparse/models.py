"""Domain models for sparse lexical analysis, BM25 encoding, and corpus statistics."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.vectorstore.models import SparseVector, VectorSearchResult


@dataclass
class TokenTerm:
    """Represents a single analyzed lexical token with its deterministic integer ID."""

    text: str
    token_id: int
    frequency: int = 1


@dataclass
class AnalyzedText:
    """Output of lexical analysis on a text string."""

    raw_text: str
    tokens: list[str]
    term_frequencies: dict[int, int]  # token_id -> frequency in document
    term_id_to_token: dict[int, str]
    doc_len: int  # Total token count


@dataclass
class TenantCorpusStats:
    """Aggregated corpus statistics for BM25 IDF calculation, strictly scoped to a tenant."""

    organization_id: UUID
    document_count: int = 0
    total_tokens: int = 0
    document_frequencies: dict[int, int] = field(default_factory=dict)  # token_id -> doc count

    @property
    def avgdl(self) -> float:
        """Average document length across the tenant's indexed corpus."""
        if self.document_count <= 0:
            return 1.0
        return self.total_tokens / self.document_count


@dataclass
class SparseRetrievalCandidate:
    """Candidate chunk identified during sparse retrieval before reciprocal rank fusion."""

    chunk_id: UUID
    document_id: UUID
    organization_id: UUID
    sparse_score: float
    rank: int
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SparseRetrievalResult:
    """Complete response from sparse vector retrieval execution."""

    query: str
    sparse_vector: SparseVector
    analyzed_tokens: list[str]
    candidates: list[VectorSearchResult]
    latency_ms: float = 0.0
