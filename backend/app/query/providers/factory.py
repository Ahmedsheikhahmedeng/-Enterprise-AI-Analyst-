"""Factory for constructing query understanding providers."""

from app.query.config import QueryUnderstandingConfig
from app.query.exceptions import QueryProviderError
from app.query.providers.base import QueryUnderstandingProvider
from app.query.providers.deterministic import DeterministicQueryUnderstandingProvider
from app.query.providers.llm import LLMQueryUnderstandingProvider


class QueryUnderstandingProviderFactory:
    """Instantiates and configures query understanding providers."""

    @staticmethod
    def create(config: QueryUnderstandingConfig) -> QueryUnderstandingProvider:
        """Create query understanding provider based on configuration."""
        if config.deterministic_mode or config.provider.lower() in (
            "deterministic",
            "deterministic_rules",
            "rules",
        ):
            return DeterministicQueryUnderstandingProvider()

        if config.provider.lower() in ("llm", "openai", "anthropic"):
            return LLMQueryUnderstandingProvider()

        raise QueryProviderError(f"Unsupported query understanding provider: '{config.provider}'.")
