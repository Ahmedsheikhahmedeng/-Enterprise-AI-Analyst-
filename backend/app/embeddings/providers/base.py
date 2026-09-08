"""Base protocol and response definitions for embedding providers."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.embeddings.models import EmbeddingVector


@dataclass
class ProviderEmbeddingResponse:
    """Standardized response returned by any EmbeddingProvider implementation."""

    vectors: list[EmbeddingVector]
    prompt_tokens: int = 0
    total_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Unified abstraction protocol for embedding providers."""

    @property
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'openai', 'local', 'azure')."""
        ...

    @property
    def model_name(self) -> str:
        """Model identifier (e.g., 'text-embedding-3-small')."""
        ...

    @property
    def dimensions(self) -> int:
        """Dimensionality of the generated vectors."""
        ...

    async def embed_texts(
        self,
        texts: Sequence[str],
    ) -> ProviderEmbeddingResponse:
        """Generate vector embeddings for a sequence of texts.

        Guarantees:
        - Result length must match input texts length.
        - Result vectors order must strictly match input texts order.
        """
        ...

    async def health_check(self) -> bool:
        """Check provider connectivity and readiness."""
        ...
