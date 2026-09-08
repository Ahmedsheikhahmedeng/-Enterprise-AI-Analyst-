"""Factory for instantiating configured cross-encoder reranker providers."""

from app.reranking.config import RerankerConfig
from app.reranking.exceptions import RerankerConfigurationError
from app.reranking.providers.base import RerankerProvider
from app.reranking.providers.local import LocalDeterministicCrossEncoderProvider
from app.reranking.providers.sentence_transformers import (
    SentenceTransformersRerankerProvider,
)


class RerankerProviderFactory:
    """Factory creating Cross-Encoder provider implementations."""

    @classmethod
    def create(cls, config: RerankerConfig) -> RerankerProvider:
        """Instantiate a provider according to the given configuration."""
        provider_name = config.provider.lower().strip()

        if provider_name in ("local", "mock"):
            return LocalDeterministicCrossEncoderProvider(
                model_name=config.model,
                version=config.version,
            )

        if provider_name in ("sentence-transformers", "transformers", "cross-encoder"):
            return SentenceTransformersRerankerProvider(
                model_name=config.model,
                version=config.version,
                device=config.device,
                max_length=config.max_input_tokens,
            )

        raise RerankerConfigurationError(
            f"Unsupported reranker provider: '{provider_name}'. "
            f"Supported providers: 'local', 'sentence-transformers'."
        )
