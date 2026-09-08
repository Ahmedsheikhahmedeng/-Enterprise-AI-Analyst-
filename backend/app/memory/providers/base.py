"""Base protocols and abstractions for memory extraction providers."""

from typing import Protocol

from app.memory.schemas import MemoryCandidate, MemorySourceType


class MemoryExtractionProvider(Protocol):
    """Protocol for extracting structured memory candidates from textual input."""

    async def extract_candidates(
        self,
        context_text: str,
        source_type: MemorySourceType = MemorySourceType.AGENT_DERIVED,
        source_id: str | None = None,
    ) -> list[MemoryCandidate]:
        """Extract validated memory candidates from context text."""
        ...
