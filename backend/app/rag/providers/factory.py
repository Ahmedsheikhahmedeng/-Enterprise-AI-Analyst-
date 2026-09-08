"""Factory for creating configured RAG generation providers."""

from app.rag.config import RAGConfig
from app.rag.providers.base import RAGLLMProvider
from app.rag.providers.gateway import GatewayRAGProvider
from app.rag.providers.local import LocalDeterministicAnswerProvider


class RAGProviderFactory:
    """Factory resolving RAGLLMProvider instances based on application configuration."""

    @classmethod
    def create(cls, config: RAGConfig) -> RAGLLMProvider:
        """Instantiate generation provider matching configured provider identifier."""
        if config.provider.lower() in ("openai", "gateway"):
            return GatewayRAGProvider(model_name=config.model)
        return LocalDeterministicAnswerProvider(model_name=config.model)
