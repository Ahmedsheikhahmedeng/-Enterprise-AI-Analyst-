"""Query deduplication based on normalized token overlap and hashing."""

import re


class QueryDeduplicator:
    """Eliminates redundant or near-identical generated query formulations."""

    _STOPWORDS = {
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "for",
        "to",
        "with",
        "at",
        "by",
        "is",
        "was",
        "what",
        "did",
        "how",
        "why",
        "في",
        "من",
        "عن",
        "على",
        "إلى",
        "ve",
        "ile",
        "için",
    }

    def _token_set(self, query: str) -> set[str]:
        words = re.findall(r"\b[\w'-]+\b", query.lower())
        return {w for w in words if w not in self._STOPWORDS and len(w) > 1}

    def deduplicate(
        self, queries: list[str], max_queries: int = 5, similarity_threshold: float = 0.85
    ) -> list[str]:
        """Return unique queries, filtering out those with Jaccard token similarity >= threshold."""
        if not queries:
            return []

        unique_queries: list[str] = []
        token_sets: list[set[str]] = []

        for q in queries:
            cleaned = q.strip()
            if not cleaned:
                continue

            tokens = self._token_set(cleaned)
            # If query has no significant content tokens, keep if not exact duplicate
            if not tokens:
                if cleaned not in unique_queries:
                    unique_queries.append(cleaned)
                continue

            # Check overlap against existing selected queries
            is_dup = False
            for existing_tokens in token_sets:
                union = tokens.union(existing_tokens)
                if not union:
                    continue
                overlap = len(tokens.intersection(existing_tokens)) / len(union)
                if overlap >= similarity_threshold:
                    is_dup = True
                    break

            if not is_dup:
                unique_queries.append(cleaned)
                token_sets.append(tokens)
                if len(unique_queries) >= max_queries:
                    break

        return unique_queries
