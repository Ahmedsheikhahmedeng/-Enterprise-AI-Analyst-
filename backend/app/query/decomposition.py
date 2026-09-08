"""Query decomposition splitting multi-part and comparison questions into atomic sub-queries."""

import re

from app.query.models import QueryIntent


class QueryDecomposer:
    """Decomposes compound questions into discrete, targeted sub-queries."""

    # Conjunction patterns splitting clauses
    _CONJUNCTION_SPLIT = re.compile(
        r"\s+(?:and\s+(?:how\s+did\s+it|what\s+was|why\s+did|how\s+does)|as\s+well\s+as|in\s+addition\s+to|وكذلك|بالإضافة\s+إلى|ayrıca|ve\s+bunun\s+yanında)\s+",
        re.I,
    )

    _YEAR_PAIR_RE = re.compile(r"\b(19\d\d|20\d\d)\b.*?\b(19\d\d|20\d\d)\b")

    def decompose(self, query: str, intent: QueryIntent, max_subqueries: int = 3) -> list[str]:
        """Decompose query into atomic sub-queries if query structure warrants it."""
        if not query or not query.strip() or max_subqueries <= 0:
            return []

        text = query.strip()
        subqueries: list[str] = []

        # 1. Multi-part conjunction splitting
        # e.g. "What was revenue in 2024 and how did it compare to 2025?"
        splits = self._CONJUNCTION_SPLIT.split(text)
        if len(splits) > 1:
            for part in splits:
                cleaned = part.strip().rstrip("?!.,;:")
                if len(cleaned.split()) >= 2:
                    subqueries.append(cleaned)
                    if len(subqueries) >= max_subqueries:
                        return subqueries

        # 2. Comparative questions spanning two years/quarters
        # e.g. "Compare revenue in 2024 and 2025" or "2024 vs 2025 revenue"
        if intent == QueryIntent.COMPARISON or not subqueries:
            m = self._YEAR_PAIR_RE.search(text)
            if m:
                year1, year2 = m.group(1), m.group(2)
                # Base topic without the years
                topic = re.sub(r"\b(19\d\d|20\d\d)\b", "", text)
                topic = re.sub(
                    r"\b(?:compare|comparison|versus|vs\.?|between|and|في|و|ve|ile)\b",
                    "",
                    topic,
                    flags=re.I,
                )
                topic = " ".join(topic.split()).strip("?!.,;:")
                if topic:
                    sub1 = f"{topic} {year1}".strip()
                    sub2 = f"{topic} {year2}".strip()
                    if sub1 not in subqueries:
                        subqueries.append(sub1)
                    if sub2 not in subqueries:
                        subqueries.append(sub2)

        return subqueries[:max_subqueries]
