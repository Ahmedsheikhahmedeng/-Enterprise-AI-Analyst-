"""Domain models for Query Understanding, Planning & Multi-Query Retrieval."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.retrieval.hybrid.models import HybridRetrievedChunk


class QueryIntent(StrEnum):
    """Classified communicative intent of the user search query."""

    FACTUAL_LOOKUP = "factual_lookup"
    COMPARISON = "comparison"
    TREND_ANALYSIS = "trend_analysis"
    DEFINITION = "definition"
    SUMMARIZATION = "summarization"
    EXPLANATION = "explanation"
    AGGREGATION = "aggregation"
    FILTER_LOOKUP = "filter_lookup"
    MULTI_PART = "multi_part"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LanguageDetectionResult:
    """Multilingual language detection result."""

    primary_language: str  # "ar", "tr", "en", "mixed", "unknown"
    detected_languages: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass(frozen=True)
class ExtractedEntity:
    """Named or structured entity extracted from query text."""

    name: str
    category: str  # e.g. "date", "year", "quarter", "currency", "percentage", "metric", "code"
    value: Any
    is_explicit: bool = True  # True if directly extracted from query; False if inferred
    confidence: float = 1.0


@dataclass(frozen=True)
class FilterHint:
    """Extracted filtering criteria separated into hard constraints vs soft hints."""

    field: str
    value: Any
    is_hard_filter: bool = False  # Hard filters restrict queries; soft hints guide relevance only


@dataclass(frozen=True)
class QueryRetrievalBudget:
    """Operational resource budget bounding multi-query execution."""

    max_queries: int = 5
    max_candidates_per_query: int = 50
    max_total_candidates: int = 150
    timeout_seconds: float = 10.0


@dataclass
class QueryDiagnostics:
    """Detailed observability and execution latency metrics for query understanding."""

    language_latency_ms: float = 0.0
    normalization_latency_ms: float = 0.0
    intent_latency_ms: float = 0.0
    entity_latency_ms: float = 0.0
    rewrite_latency_ms: float = 0.0
    expansion_latency_ms: float = 0.0
    decomposition_latency_ms: float = 0.0
    total_understanding_ms: float = 0.0
    provider: str = "deterministic"
    model: str = "rules-v1"
    prompt_version: str = "v1"
    tokens_used: int = 0
    cost_usd: float = 0.0
    is_degraded: bool = False
    degradation_reason: str | None = None


@dataclass
class QueryAnalysis:
    """Comprehensive semantic analysis of an input query before planning."""

    original_query: str
    normalized_query: str
    language: str
    detected_languages: list[str] = field(default_factory=list)
    intent: QueryIntent = QueryIntent.UNKNOWN
    entities: list[ExtractedEntity] = field(default_factory=list)
    rewritten_query: str | None = None
    expanded_queries: list[str] = field(default_factory=list)
    sub_queries: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class SearchPlan:
    """Complete actionable plan for orchestrating multi-query hybrid retrieval."""

    original_query: str
    primary_query: str
    alternative_queries: list[str] = field(default_factory=list)
    sub_queries: list[str] = field(default_factory=list)
    language: str = "en"
    detected_languages: list[str] = field(default_factory=list)
    intent: QueryIntent = QueryIntent.UNKNOWN
    entities: list[ExtractedEntity] = field(default_factory=list)
    hard_filters: dict[str, Any] = field(default_factory=dict)
    soft_filters: dict[str, Any] = field(default_factory=dict)
    retrieval_budget: QueryRetrievalBudget = field(default_factory=QueryRetrievalBudget)
    confidence: float = 1.0
    diagnostics: QueryDiagnostics = field(default_factory=QueryDiagnostics)

    @property
    def all_queries(self) -> list[str]:
        """Return unique ordered list of all planned search queries to execute."""
        queries: list[str] = [self.primary_query]
        for q in self.alternative_queries:
            if q not in queries:
                queries.append(q)
        for q in self.sub_queries:
            if q not in queries:
                queries.append(q)
        return queries[: self.retrieval_budget.max_queries]


@dataclass
class MultiQueryRetrievalResult:
    """Domain response for multi-query execution containing fused and reranked chunks."""

    original_query: str
    search_plan: SearchPlan
    chunks: list[HybridRetrievedChunk]
    retrieval_mode: str = "multi_query_hybrid_reranked"
    total_results: int = 0
    total_latency_ms: float = 0.0
