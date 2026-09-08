"""Memory extraction coordinator enforcing privacy and provenance on candidates."""

from app.memory.exceptions import MemoryPrivacyViolationError
from app.memory.policies import MemoryPrivacyFilter
from app.memory.provenance import MemoryProvenanceTracker
from app.memory.providers.base import MemoryExtractionProvider
from app.memory.providers.deterministic import DeterministicMemoryExtractor
from app.memory.schemas import MemoryCandidate, MemorySourceType


class MemoryExtractor:
    """Extracts, sanitizes, and validates memory candidates from raw text."""

    def __init__(self, provider: MemoryExtractionProvider | None = None) -> None:
        self.provider = provider or DeterministicMemoryExtractor()
        self.provenance_tracker = MemoryProvenanceTracker()

    async def extract_from_text(
        self,
        text: str,
        source_type: MemorySourceType = MemorySourceType.AGENT_DERIVED,
        source_id: str | None = None,
    ) -> list[MemoryCandidate]:
        """Extract memory candidates and reject candidates containing sensitive credentials."""
        raw_candidates = await self.provider.extract_candidates(
            context_text=text,
            source_type=source_type,
            source_id=source_id,
        )

        valid_candidates: list[MemoryCandidate] = []
        for cand in raw_candidates:
            # 1. Privacy filter check
            try:
                MemoryPrivacyFilter.enforce(cand.content)
            except MemoryPrivacyViolationError:
                # Discard candidate containing forbidden secrets
                continue

            # 2. Provenance validation
            self.provenance_tracker.validate_candidate_provenance(cand)
            valid_candidates.append(cand)

        return valid_candidates
