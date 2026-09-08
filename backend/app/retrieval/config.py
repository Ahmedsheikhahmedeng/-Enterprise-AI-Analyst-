"""Retrieval configuration and parameter defaults."""

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class RetrievalConfig:
    """Configures dense retrieval behavior and security guardrails."""

    default_top_k: int = 10
    max_top_k: int = 50
    min_query_characters: int = 2
    max_query_characters: int = 2000
    max_query_tokens: int = 512
    score_threshold: float | None = None
    parent_context_enabled: bool = True
    timeout_seconds: float = 10.0

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "RetrievalConfig":
        s = settings or get_settings()
        return cls(
            default_top_k=s.RETRIEVAL_DEFAULT_TOP_K,
            max_top_k=s.RETRIEVAL_MAX_TOP_K,
            min_query_characters=s.RETRIEVAL_MIN_QUERY_CHARACTERS,
            max_query_characters=s.RETRIEVAL_MAX_QUERY_CHARACTERS,
            max_query_tokens=s.RETRIEVAL_MAX_QUERY_TOKENS,
            score_threshold=s.RETRIEVAL_SCORE_THRESHOLD,
            parent_context_enabled=s.RETRIEVAL_PARENT_CONTEXT_ENABLED,
            timeout_seconds=s.RETRIEVAL_TIMEOUT_SECONDS,
        )


@dataclass(frozen=True)
class BM25Config:
    """Configures Okapi BM25 scoring and sparse analyzer settings."""

    k1: float = 1.2
    b: float = 0.75
    version: str = "bm25-v1"
    strip_arabic_diacritics: bool = True

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "BM25Config":
        s = settings or get_settings()
        return cls(
            k1=s.BM25_K1,
            b=s.BM25_B,
            version=s.SPARSE_INDEX_VERSION,
            strip_arabic_diacritics=s.SPARSE_STRIP_ARABIC_DIACRITICS,
        )


@dataclass(frozen=True)
class HybridRetrievalConfig:
    """Configures hybrid retrieval orchestration, candidate bounds, and RRF."""

    enabled: bool = True
    default_top_k: int = 10
    max_top_k: int = 50
    dense_candidate_k: int = 50
    sparse_candidate_k: int = 50
    rrf_k: int = 60
    allow_partial_failure: bool = True
    timeout_seconds: float = 15.0
    bm25: BM25Config = BM25Config()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "HybridRetrievalConfig":
        s = settings or get_settings()
        return cls(
            enabled=s.HYBRID_RETRIEVAL_ENABLED,
            default_top_k=s.HYBRID_DEFAULT_TOP_K,
            max_top_k=s.HYBRID_MAX_TOP_K,
            dense_candidate_k=s.HYBRID_DENSE_CANDIDATE_K,
            sparse_candidate_k=s.HYBRID_SPARSE_CANDIDATE_K,
            rrf_k=s.HYBRID_RRF_K,
            allow_partial_failure=s.HYBRID_ALLOW_PARTIAL_FAILURE,
            timeout_seconds=s.RETRIEVAL_TIMEOUT_SECONDS,
            bm25=BM25Config.from_settings(s),
        )


def get_retrieval_config() -> RetrievalConfig:
    """Factory helper to obtain current retrieval config from settings."""
    return RetrievalConfig.from_settings()


def get_hybrid_retrieval_config() -> HybridRetrievalConfig:
    """Factory helper to obtain current hybrid retrieval config from settings."""
    return HybridRetrievalConfig.from_settings()
