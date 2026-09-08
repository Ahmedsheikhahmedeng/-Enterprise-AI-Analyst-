"""Protocol interface for query understanding providers."""

from typing import Protocol

from app.query.models import QueryAnalysis


class QueryUnderstandingProvider(Protocol):
    """Abstract protocol for query understanding and semantic planning providers."""

    provider_name: str
    model_name: str
    version: str

    async def analyze(
        self,
        query: str,
        *,
        enable_rewrite: bool = True,
        enable_expansion: bool = True,
        enable_decomposition: bool = True,
        max_alternatives: int = 3,
        max_subqueries: int = 3,
    ) -> QueryAnalysis:
        """Perform semantic analysis, entity extraction, rewriting, and planning on input query."""
        ...

    async def health_check(self) -> bool:
        """Verify provider availability."""
        ...
