"""Configuration models and settings binding for Cross-Encoder Reranking."""

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class RerankerConfig:
    """Immutable runtime configuration for cross-encoder reranking."""

    enabled: bool = True
    provider: str = "local"
    model: str = "local-cross-encoder-v1"
    version: str = "reranker-v1"
    device: str = "auto"
    batch_size: int = 16
    max_candidates: int = 50
    final_k: int = 10
    max_input_tokens: int = 512
    timeout_seconds: float = 10.0
    max_concurrent_batches: int = 2
    allow_fallback: bool = True

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "RerankerConfig":
        """Build RerankerConfig instance from application Settings."""
        s = settings or get_settings()
        return cls(
            enabled=s.RERANKING_ENABLED,
            provider=s.RERANKER_PROVIDER.strip().lower(),
            model=s.RERANKER_MODEL.strip(),
            version=s.RERANKER_VERSION.strip(),
            device=s.RERANKER_DEVICE.strip().lower(),
            batch_size=s.RERANKER_BATCH_SIZE,
            max_candidates=s.RERANKER_MAX_CANDIDATES,
            final_k=s.RERANKER_FINAL_K,
            max_input_tokens=s.RERANKER_MAX_INPUT_TOKENS,
            timeout_seconds=s.RERANKER_TIMEOUT_SECONDS,
            max_concurrent_batches=s.RERANKER_MAX_CONCURRENT_BATCHES,
            allow_fallback=s.RERANKER_ALLOW_FALLBACK,
        )


def get_reranker_config() -> RerankerConfig:
    """Factory helper to obtain current reranker config from global settings."""
    return RerankerConfig.from_settings()
