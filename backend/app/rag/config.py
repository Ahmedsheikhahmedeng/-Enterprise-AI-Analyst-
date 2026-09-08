"""Configuration models and resolvers for evidence-grounded RAG."""

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class RAGConfig:
    """Strongly typed immutable configuration bounding RAG orchestration and generation."""

    enabled: bool
    provider: str
    model: str
    api_key: str | None
    base_url: str | None
    temperature: float
    max_output_tokens: int
    max_context_tokens: int
    evidence_top_k: int
    min_evidence_score: float
    timeout_seconds: float
    max_retries: int
    prompt_version: str
    response_language: str
    max_cost_per_request: float

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "RAGConfig":
        """Build RAGConfig dataclass from application settings."""
        s = settings or get_settings()
        return cls(
            enabled=s.RAG_ENABLED,
            provider=s.RAG_LLM_PROVIDER,
            model=s.RAG_LLM_MODEL,
            api_key=s.RAG_LLM_API_KEY,
            base_url=s.RAG_LLM_BASE_URL,
            temperature=s.RAG_LLM_TEMPERATURE,
            max_output_tokens=s.RAG_MAX_OUTPUT_TOKENS,
            max_context_tokens=s.RAG_MAX_CONTEXT_TOKENS,
            evidence_top_k=s.RAG_EVIDENCE_TOP_K,
            min_evidence_score=s.RAG_MIN_EVIDENCE_SCORE,
            timeout_seconds=s.RAG_LLM_TIMEOUT_SECONDS,
            max_retries=s.RAG_LLM_MAX_RETRIES,
            prompt_version=s.RAG_PROMPT_VERSION,
            response_language=s.RAG_RESPONSE_LANGUAGE,
            max_cost_per_request=s.RAG_MAX_LLM_COST_PER_REQUEST,
        )


def get_rag_config() -> RAGConfig:
    """Return RAG configuration instance initialized from current environment."""
    return RAGConfig.from_settings()
