"""Configuration settings for Secure SQL Agent & Structured Data Analysis."""

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class SQLAgentConfig:
    """Strongly typed immutable configuration for SQL Agent pipeline."""

    enabled: bool
    provider: str
    model: str
    statement_timeout_ms: int
    query_timeout_seconds: float
    max_rows: int
    max_result_bytes: int
    max_joins: int
    max_ctes: int
    max_subquery_depth: int
    schema_cache_ttl_seconds: int
    prompt_version: str
    max_llm_cost_per_request: float
    api_key: str | None = None
    base_url: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "SQLAgentConfig":
        """Instantiate SQLAgentConfig from application environment settings."""
        cfg = settings or get_settings()
        return cls(
            enabled=cfg.SQL_AGENT_ENABLED,
            provider=cfg.SQL_LLM_PROVIDER,
            model=cfg.SQL_LLM_MODEL,
            statement_timeout_ms=cfg.SQL_STATEMENT_TIMEOUT_MS,
            query_timeout_seconds=cfg.SQL_QUERY_TIMEOUT_SECONDS,
            max_rows=cfg.SQL_MAX_ROWS,
            max_result_bytes=cfg.SQL_MAX_RESULT_BYTES,
            max_joins=cfg.SQL_MAX_JOINS,
            max_ctes=cfg.SQL_MAX_CTES,
            max_subquery_depth=cfg.SQL_MAX_SUBQUERY_DEPTH,
            schema_cache_ttl_seconds=cfg.SQL_SCHEMA_CACHE_TTL_SECONDS,
            prompt_version=cfg.SQL_PROMPT_VERSION,
            max_llm_cost_per_request=cfg.SQL_MAX_LLM_COST_PER_REQUEST,
            api_key=cfg.SQL_LLM_API_KEY,
            base_url=cfg.SQL_LLM_BASE_URL,
        )


def get_sql_agent_config() -> SQLAgentConfig:
    """Return SQLAgentConfig resolved from global settings."""
    return SQLAgentConfig.from_settings()
