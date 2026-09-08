"""Deterministic scoring and ranking of retrieved memory items."""

import math
from datetime import UTC, datetime
from typing import Any

from app.memory.config import MemoryConfig, get_memory_config
from app.memory.schemas import MemorySourceType, MemoryVisibility

SOURCE_RELIABILITY_WEIGHTS: dict[str, float] = {
    MemorySourceType.SYSTEM_VERIFIED.value: 1.0,
    MemorySourceType.USER_DECLARED.value: 0.9,
    MemorySourceType.DOCUMENT_DERIVED.value: 0.85,
    MemorySourceType.AGENT_DERIVED.value: 0.75,
}

VISIBILITY_SPECIFICITY_BONUS: dict[str, float] = {
    MemoryVisibility.SESSION.value: 0.15,
    MemoryVisibility.USER.value: 0.10,
    MemoryVisibility.PRIVATE.value: 0.10,
    MemoryVisibility.ORGANIZATION.value: 0.05,
}


class MemoryRanker:
    """Calculates multidimensional composite relevance score for memory items."""

    def __init__(self, config: MemoryConfig | None = None) -> None:
        self.config = config or get_memory_config()

    def score_memory(
        self,
        memory_item: Any,
        semantic_similarity: float = 0.5,
        target_session_id: Any | None = None,
        now: datetime | None = None,
    ) -> tuple[float, dict[str, float]]:
        """Compute composite relevance score in [0.0, 1.0] and return score breakdown."""
        current_time = now or datetime.now(UTC)

        # 1. Recency Decay (exponential half-life)
        created_at = memory_item.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_days = max(0.0, (current_time - created_at).total_seconds() / 86400.0)
        half_life = self.config.recency_half_life_days
        recency_factor = math.exp(-0.693 * (age_days / half_life))

        # 2. Source Reliability
        source_rel = SOURCE_RELIABILITY_WEIGHTS.get(str(memory_item.source_type), 0.75)

        # 3. Scope / Specificity
        vis_bonus = VISIBILITY_SPECIFICITY_BONUS.get(str(memory_item.visibility), 0.05)
        if target_session_id and getattr(memory_item, "session_id", None) == target_session_id:
            vis_bonus += 0.10

        # Weighted combination:
        # Semantic similarity: 40%
        # Importance: 20%
        # Confidence: 20%
        # Recency: 10%
        # Source Reliability: 10%
        importance = getattr(memory_item, "importance", 0.5)
        confidence = getattr(memory_item, "confidence", 1.0)

        raw_score = (
            (semantic_similarity * 0.40)
            + (importance * 0.20)
            + (confidence * 0.20)
            + (recency_factor * 0.10)
            + (source_rel * 0.10)
            + vis_bonus
        )

        clamped = max(0.0, min(1.0, raw_score))

        breakdown = {
            "semantic_similarity": round(semantic_similarity, 4),
            "importance": round(importance, 4),
            "confidence": round(confidence, 4),
            "recency_factor": round(recency_factor, 4),
            "source_reliability": round(source_rel, 4),
            "scope_bonus": round(vis_bonus, 4),
            "composite_score": round(clamped, 4),
        }

        return clamped, breakdown
