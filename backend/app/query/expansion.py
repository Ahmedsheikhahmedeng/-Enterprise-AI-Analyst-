"""Domain-specific query expansion and synonym generation across languages."""

import re


class QueryExpander:
    """Generates precise domain synonyms and alternative formulations."""

    # English domain expansions
    _EN_SYNONYMS = {
        "decline": ["decrease", "drop", "reduction", "deterioration"],
        "increase": ["growth", "rise", "expansion", "improvement"],
        "operating margin": [
            "operating profitability",
            "operating margin ratio",
            "operating profit",
        ],
        "revenue": ["sales", "turnover", "total revenue", "top line"],
        "profit": ["net income", "earnings", "profitability"],
        "expenses": ["operating costs", "expenditure", "overhead"],
    }

    # Arabic domain expansions
    _AR_SYNONYMS = {
        "انخفاض": ["تراجع", "هبوط", "تناقص"],
        "ارتفاع": ["نمو", "زيادة", "تحسن"],
        "هامش التشغيل": ["الربحية التشغيلية", "هامش الأرباح التشغيلية"],
        "الإيرادات": ["المبيعات", "حجم الأعمال", "الدخل الإجمالي"],
    }

    # Turkish domain expansions
    _TR_SYNONYMS = {
        "düşüş": ["azalış", "gerileme", "daralma"],
        "artış": ["büyüme", "yükseliş", "kazanç"],
        "faaliyet marjı": ["faaliyet kârlılığı", "operasyonel marj"],
        "gelir": ["hasılat", "satışlar", "ciro"],
    }

    def expand(self, query: str, language: str, max_expansions: int = 3) -> list[str]:
        """Generate alternative query formulations substituting key domain terms."""
        if not query or not query.strip() or max_expansions <= 0:
            return []

        expansions: list[str] = []
        syn_dict = self._EN_SYNONYMS
        if language == "ar":
            syn_dict = self._AR_SYNONYMS
        elif language == "tr":
            syn_dict = self._TR_SYNONYMS
        elif language == "mixed":
            # Combine
            syn_dict = {**self._EN_SYNONYMS, **self._AR_SYNONYMS, **self._TR_SYNONYMS}

        query_text = query.strip()
        query_lower = query_text.lower()

        for term, replacements in syn_dict.items():
            if term in query_lower:
                # Replace term with each synonym
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                for repl in replacements:
                    alt = pattern.sub(repl, query_text).strip()
                    if alt.lower() != query_lower and alt not in expansions:
                        expansions.append(alt)
                        if len(expansions) >= max_expansions:
                            return expansions

        return expansions
