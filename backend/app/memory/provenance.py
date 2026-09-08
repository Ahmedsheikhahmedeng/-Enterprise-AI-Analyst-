"""Provenance tracking and validation for Enterprise Agent Memory."""

from typing import Any

from app.memory.exceptions import MemoryValidationError
from app.memory.schemas import MemoryCandidate, MemorySourceType


class MemoryProvenanceTracker:
    """Validates and attaches provenance chains to extracted memory candidates."""

    @staticmethod
    def validate_candidate_provenance(candidate: MemoryCandidate) -> None:
        """Ensure derived memories carry valid source references."""
        # User declared memory does not strictly require external source_id
        if candidate.source_type == MemorySourceType.USER_DECLARED:
            return

        # Derived memories must reference either source_id or have non-empty source_refs
        if not candidate.source_id and not candidate.source_refs:
            raise MemoryValidationError(
                f"Derived memory of type '{candidate.source_type}' must reference source_id or source_refs."
            )

    @staticmethod
    def create_provenance_ref(
        source_type: str,
        source_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Construct structured reference dictionary."""
        return {
            "source_type": source_type,
            "source_id": source_id,
            "metadata": metadata or {},
        }
