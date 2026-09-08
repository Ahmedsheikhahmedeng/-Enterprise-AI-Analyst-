"""Provider factory for constructing configured embedding providers."""

from app.embeddings.config import EmbeddingConfig
from app.embeddings.exceptions import EmbeddingConfigurationError
from app.embeddings.providers.base import EmbeddingProvider
from app.embeddings.providers.local import LocalDeterministicEmbeddingProvider
from app.embeddings.providers.openai import OpenAIEmbeddingProvider


class EmbeddingProviderFactory:
    """Factory to instantiate and configure embedding providers."""

    _REGISTRY: dict[str, type[EmbeddingProvider]] = {
        "local": LocalDeterministicEmbeddingProvider,
        "openai": OpenAIEmbeddingProvider,
        "mock": LocalDeterministicEmbeddingProvider,
    }

    @classmethod
    def create(cls, config: EmbeddingConfig) -> EmbeddingProvider:
        """Create an embedding provider based on configuration.

        Raises:
            EmbeddingConfigurationError: If provider is unsupported or config is invalid.
        """
        provider_name = config.provider.lower().strip()

        if provider_name == "local" or provider_name == "mock":
            return LocalDeterministicEmbeddingProvider(
                model_name=config.model,
                dimensions=config.dimensions,
            )

        if provider_name == "openai":
            return OpenAIEmbeddingProvider(
                api_key=config.api_key,
                model_name=config.model,
                dimensions=config.dimensions,
                base_url=config.api_base_url,
                timeout_seconds=config.timeout_seconds,
                max_retries=config.max_retries,
                retry_backoff_factor=config.retry_backoff_factor,
            )

        supported = ", ".join(sorted(cls._REGISTRY.keys()))
        raise EmbeddingConfigurationError(
            f"Unsupported embedding provider: '{provider_name}'. Supported providers: {supported}."
        )
