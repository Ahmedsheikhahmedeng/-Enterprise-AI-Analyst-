"""Deduplication and conflict detection for Enterprise Agent Memory."""

import re
from enum import StrEnum
from typing import Any

from app.memory.config import MemoryConfig, get_memory_config
from app.memory.normalization import compute_content_hash
from app.memory.schemas import MemoryCandidate, MemorySourceType


class ConflictResolution(StrEnum):
    """Outcome of conflict analysis between memory candidate and existing records."""

    NONE = "none"  # No conflict
    SUPERSEDES = "supersedes"  # Candidate supersedes existing older/lower-confidence memory
    CONFLICT = "conflict"  # Contradictory claims requiring explicit operator resolution


class MemoryDeduplicator:
    """Detects exact and near-duplicate memory items."""

    def __init__(self, config: MemoryConfig | None = None) -> None:
        self.config = config or get_memory_config()

    @staticmethod
    def is_exact_duplicate(content_hash_a: str, content_hash_b: str) -> bool:
        """Check if content hashes are identical."""
        return content_hash_a == content_hash_b

    def is_semantic_duplicate(self, similarity: float) -> bool:
        """Check if similarity exceeds deduplication threshold."""
        return similarity >= self.config.similarity_dedup_threshold


class MemoryConflictDetector:
    """Detects opposing facts and manages versioned supersession."""

    @staticmethod
    def check_conflict(
        candidate: MemoryCandidate,
        existing_item: Any,
    ) -> tuple[ConflictResolution, str | None]:
        """Analyze if candidate conflicts with or supersedes an existing active memory."""
        # 1. Exact match is duplicate, not conflict
        cand_hash = compute_content_hash(candidate.content)
        if cand_hash == getattr(existing_item, "content_hash", ""):
            return ConflictResolution.NONE, None

        # 2. Check for explicit topic key collision or temporal opposing pattern
        # e.g. "Fiscal year starts in January" vs "Fiscal year starts in April"
        # Extract common patterns (numbers, months, quarters, statuses)
        c_text = candidate.content.lower()
        e_text = getattr(existing_item, "content", "").lower()

        # Simple semantic key matching: shared nouns/topics but distinct values
        tokens_c = set(re.findall(r"\b[a-z]{4,}\b", c_text))
        tokens_e = set(re.findall(r"\b[a-z]{4,}\b", e_text))
        overlap = tokens_c.intersection(tokens_e)

        # High overlap in topic tokens (>60% of both) with different hashes
        if len(overlap) >= 3 and len(overlap) / max(len(tokens_c), len(tokens_e)) >= 0.5:
            # Check source reliability: System verified or User declared supersedes Agent derived
            c_source = candidate.source_type
            e_source = getattr(existing_item, "source_type", "")

            if c_source in (MemorySourceType.SYSTEM_VERIFIED, MemorySourceType.USER_DECLARED) and (
                e_source == MemorySourceType.AGENT_DERIVED
            ):
                return (
                    ConflictResolution.SUPERSEDES,
                    f"Candidate from '{c_source}' supersedes derived memory.",
                )

            if candidate.confidence > getattr(existing_item, "confidence", 0.5) + 0.2:
                return (
                    ConflictResolution.SUPERSEDES,
                    "Candidate has significantly higher confidence.",
                )

            return ConflictResolution.CONFLICT, "Opposing claims detected on shared topic."

        return ConflictResolution.NONE, None
