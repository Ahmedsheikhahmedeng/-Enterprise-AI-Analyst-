"""Protocol and interface definitions for cross-encoder reranker providers."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class RerankerProvider(Protocol):
    """Protocol defining the required capabilities of a Cross-Encoder provider."""

    @property
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'local', 'sentence-transformers')."""
        ...

    @property
    def model_name(self) -> str:
        """Name or HuggingFace ID of the cross-encoder model."""
        ...

    @property
    def version(self) -> str:
        """Version identifier for provenance tracking."""
        ...

    @property
    def device(self) -> str:
        """Execution device ('cpu', 'cuda', 'mps')."""
        ...

    async def score_pairs(
        self,
        pairs: Sequence[tuple[str, str]],
    ) -> list[float]:
        """Compute relevance scores for a sequence of (query, candidate_text) pairs.

        Guarantees:
        - Output list length strictly matches input pairs length.
        - Output list ordering strictly matches input pairs ordering.
        - Scores are floats where higher value indicates stronger relevance.
        """
        ...

    async def health_check(self) -> bool:
        """Verify model readiness and runtime health."""
        ...
