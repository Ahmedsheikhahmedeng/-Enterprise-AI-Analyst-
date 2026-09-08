"""Query rewriting engine formulating search-oriented expressions."""

import re

from app.query.models import QueryIntent


class QueryRewriter:
    """Transforms ambiguous, conversational, or terse queries into rich retrieval formulations."""

    _TERSE_FINANCIAL_MAP = {
        "revenue": "revenue financial performance revenue amount sales",
        "margin": "operating margin operating profitability margin percentage",
        "profit": "net profit operating income financial earnings",
        "ebitda": "ebitda operating cash earnings before interest tax",
        "cost": "operating expenses cost of goods sold expenditure",
        "إيرادات": "الإيرادات الأداء المالي حجم المبيعات والدخل",
        "هامش": "هامش التشغيل الربحية التشغيلية ونسبة الهامش",
        "gelir": "gelir finansal performans hasılat satış tutarı",
        "marj": "faaliyet marjı operasyonel kârlılık marj oranı",
    }

    _CONVERSATIONAL_PREFIXES = [
        re.compile(r"^(?:can you\s+)?tell me about\s+", re.I),
        re.compile(r"^(?:please\s+)?give me\s+(?:the\s+)?", re.I),
        re.compile(r"^(?:what do you know about|show me)\s+", re.I),
        re.compile(r"^(?:من فضلك\s+)?أخبرني عن\s+", re.I),
        re.compile(r"^(?:lütfen\s+)?bana\s+(?:hakkında\s+)?bilgi ver\s+", re.I),
    ]

    def rewrite(self, query: str, intent: QueryIntent) -> str | None:
        """Produce search formulation, or None if query is already specific and complete."""
        if not query or not query.strip():
            return None

        text = query.strip()
        cleaned = text.rstrip("?!.,;:")

        # 1. Strip conversational filler prefixes
        stripped = cleaned
        for pat in self._CONVERSATIONAL_PREFIXES:
            stripped = pat.sub("", stripped).strip()

        # 2. Check for terse single-word or two-word metric queries (e.g. "revenue?", "margin?")
        words = stripped.lower().split()
        if len(words) <= 2:
            key = words[0]
            if key in self._TERSE_FINANCIAL_MAP:
                return self._TERSE_FINANCIAL_MAP[key]

        # 3. If conversational filler was removed, return stripped clean query
        if stripped.lower() != text.lower() and len(stripped) >= 3:
            return stripped

        # 4. If intent is explanation or definition, enrich query search terms
        if intent == QueryIntent.EXPLANATION and (
            "why" in words or "لماذا" in stripped or "neden" in words
        ):
            # e.g. "why did revenue decline" -> "causes factors revenue decline decrease"
            return f"{stripped} causes drivers factors explanation"

        return None
