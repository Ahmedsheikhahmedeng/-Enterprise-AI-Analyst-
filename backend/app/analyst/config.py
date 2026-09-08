"""Configuration settings for the Unified AI Analyst Orchestrator."""

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass
class AnalystConfig:
    """Encapsulated runtime configuration for unified multi-source analysis."""

    enabled: bool = True
    planner_provider: str = "deterministic"
    total_timeout_seconds: float = 25.0
    sql_timeout_seconds: float = 10.0
    rag_timeout_seconds: float = 15.0
    max_branches: int = 4
    max_total_queries: int = 6
    max_evidence: int = 20
    max_context_tokens: int = 6000
    prompt_version: str = "analyst-v1.0"

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "AnalystConfig":
        """Build AnalystConfig instance from application Settings."""
        s = settings or get_settings()
        return cls(
            enabled=s.ANALYST_ENABLED,
            planner_provider=s.ANALYST_PLANNER_PROVIDER,
            total_timeout_seconds=s.ANALYST_TOTAL_TIMEOUT_SECONDS,
            sql_timeout_seconds=s.ANALYST_SQL_TIMEOUT_SECONDS,
            rag_timeout_seconds=s.ANALYST_RAG_TIMEOUT_SECONDS,
            max_branches=s.ANALYST_MAX_BRANCHES,
            max_total_queries=s.ANALYST_MAX_TOTAL_QUERIES,
            max_evidence=s.ANALYST_MAX_EVIDENCE,
            max_context_tokens=s.ANALYST_MAX_CONTEXT_TOKENS,
            prompt_version=s.ANALYST_PROMPT_VERSION,
        )


def get_analyst_config() -> AnalystConfig:
    """Convenience helper to retrieve default analyst config."""
    return AnalystConfig.from_settings()
