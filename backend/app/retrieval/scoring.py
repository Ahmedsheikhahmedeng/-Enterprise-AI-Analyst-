"""Score handling and threshold filtering for retrieved candidates."""

from collections.abc import Sequence

from app.vectorstore.models import VectorSearchResult


class ScoreProcessor:
    """Processes vector search scores while preserving raw engine distance metrics.

    Ensures scores are never artificially normalized or compressed, preserving
    the exact mathematical characteristics of the active vector distance metric.
    """

    @classmethod
    def filter_and_sort(
        cls,
        candidates: Sequence[VectorSearchResult],
        score_threshold: float | None = None,
    ) -> list[VectorSearchResult]:
        """Filter candidates by score threshold and ensure descending order by score."""
        filtered: list[VectorSearchResult] = []
        for cand in candidates:
            if score_threshold is not None and cand.score < score_threshold:
                continue
            filtered.append(cand)

        # Qdrant returns results sorted, but defensively re-sort descending by score
        filtered.sort(key=lambda c: c.score, reverse=True)
        return filtered
