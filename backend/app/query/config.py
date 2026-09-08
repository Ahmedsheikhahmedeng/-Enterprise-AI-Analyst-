"""Domain configuration for Query Understanding, Rewriting & Multi-Query Retrieval."""

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class QueryUnderstandingConfig:
    """Immutable operational configuration for Query Understanding and Planning."""

    enabled: bool = True
    rewrite_enabled: bool = True
    expansion_enabled: bool = True
    decomposition_enabled: bool = True
    deterministic_mode: bool = False
    provider: str = "deterministic"
    max_alternative_queries: int = 3
    max_subqueries: int = 3
    max_total_queries: int = 5
    timeout_seconds: float = 3.0
    total_pipeline_timeout_seconds: float = 15.0
    llm_max_tokens: int = 512
    confidence_threshold: float = 0.5
    prompt_version: str = "v1"

    @classmethod
    def from_settings(cls) -> "QueryUnderstandingConfig":
        """Construct domain config from global application settings."""
        settings = get_settings()
        return cls(
            enabled=settings.QUERY_UNDERSTANDING_ENABLED,
            rewrite_enabled=settings.QUERY_REWRITE_ENABLED,
            expansion_enabled=settings.QUERY_EXPANSION_ENABLED,
            decomposition_enabled=settings.QUERY_DECOMPOSITION_ENABLED,
            deterministic_mode=settings.QUERY_DETERMINISTIC_MODE,
            provider=settings.QUERY_UNDERSTANDING_PROVIDER,
            max_alternative_queries=settings.QUERY_MAX_ALTERNATIVE_QUERIES,
            max_subqueries=settings.QUERY_MAX_SUBQUERIES,
            max_total_queries=settings.QUERY_MAX_TOTAL_QUERIES,
            timeout_seconds=settings.QUERY_UNDERSTANDING_TIMEOUT_SECONDS,
            total_pipeline_timeout_seconds=settings.QUERY_TOTAL_PIPELINE_TIMEOUT_SECONDS,
            llm_max_tokens=settings.QUERY_LLM_MAX_TOKENS,
            confidence_threshold=settings.QUERY_ANALYSIS_CONFIDENCE_THRESHOLD,
            prompt_version=settings.QUERY_REWRITE_PROMPT_VERSION,
        )


def get_query_understanding_config() -> QueryUnderstandingConfig:
    """Convenience accessor for current query understanding configuration."""
    return QueryUnderstandingConfig.from_settings()
