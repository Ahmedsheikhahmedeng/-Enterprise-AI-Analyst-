"""Embedding configuration models and utilities."""

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class EmbeddingConfig:
    """Immutable domain configuration for the embedding subsystem."""

    provider: str
    model: str
    dimensions: int
    batch_size: int
    max_input_tokens: int
    timeout_seconds: float
    max_retries: int
    retry_backoff_factor: float
    normalize: bool
    cache_enabled: bool
    cache_ttl_seconds: int
    max_concurrent_requests: int
    api_key: str | None
    api_base_url: str | None
    version: str

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "EmbeddingConfig":
        s = settings or get_settings()
        return cls(
            provider=s.EMBEDDING_PROVIDER.lower().strip(),
            model=s.EMBEDDING_MODEL.strip(),
            dimensions=s.EMBEDDING_DIMENSIONS,
            batch_size=s.EMBEDDING_BATCH_SIZE,
            max_input_tokens=s.EMBEDDING_MAX_INPUT_TOKENS,
            timeout_seconds=s.EMBEDDING_TIMEOUT_SECONDS,
            max_retries=s.EMBEDDING_MAX_RETRIES,
            retry_backoff_factor=s.EMBEDDING_RETRY_BACKOFF_FACTOR,
            normalize=s.EMBEDDING_NORMALIZE,
            cache_enabled=s.EMBEDDING_CACHE_ENABLED,
            cache_ttl_seconds=s.EMBEDDING_CACHE_TTL_SECONDS,
            max_concurrent_requests=s.EMBEDDING_MAX_CONCURRENT_REQUESTS,
            api_key=s.EMBEDDING_API_KEY,
            api_base_url=s.EMBEDDING_API_BASE_URL,
            version=s.EMBEDDING_VERSION.strip(),
        )
