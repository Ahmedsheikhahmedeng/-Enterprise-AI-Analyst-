"""Enterprise intent classification for search queries across Arabic, Turkish, and English."""

import re

from app.query.models import QueryIntent


class IntentClassifier:
    """Classifies user query intent using enterprise domain lexical patterns."""

    _COMPARISON_PATTERNS = [
        re.compile(r"\b(?:compare|comparison|versus|vs\.?|difference between)\b", re.I),
        re.compile(r"\b(?:مقارنة|قارن|الفرق بين|مقابل)\b", re.I),
        re.compile(
            r"\b(?:karşılaştır|karsilastir|kıyasla|farkı nedir|ile .+ arasındaki fark)\b", re.I
        ),
    ]

    _EXPLANATION_PATTERNS = [
        re.compile(
            r"\b(?:why|how come|cause of|caused by|caused|causes|reason for|explain)\b", re.I
        ),
        re.compile(r"\b(?:لماذا|ما سبب|ما اسباب|ما هي أسباب|علل|فسر|كيف أثر)\b", re.I),
        re.compile(r"\b(?:neden|niçin|sebebi nedir|nasıl oldu|açıkla|nedeni neydi)\b", re.I),
    ]

    _SUMMARIZATION_PATTERNS = [
        re.compile(r"\b(?:summarize|summary|overview|brief|executive summary)\b", re.I),
        re.compile(r"\b(?:لخص|تلخيص|ملخص|نبذة|إيجاز)\b", re.I),
        re.compile(r"\b(?:özetle|ozetle|özet|genel bakış|ana hatlarıyla)\b", re.I),
    ]

    _TREND_PATTERNS = [
        re.compile(
            r"\b(?:trend|trajectory|evolution|historical|growth over time|decline over time)\b",
            re.I,
        ),
        re.compile(r"\b(?:تطور|اتجاه|تاريخي|مسار|تغير عبر السنوات)\b", re.I),
        re.compile(r"\b(?:trend|eğilim|zaman içindeki değişim|yıllara göre gelişim)\b", re.I),
    ]

    _DEFINITION_PATTERNS = [
        re.compile(r"^(?:what is|define|meaning of)\s+[a-zA-Z\s]{1,25}\??$", re.I),
        re.compile(r"\b(?:definition of|meaning of)\b", re.I),
        re.compile(r"^(?:ما هو|ما هي|ما المقصود ب|تعريف|معنى)\s+[\u0600-\u06FF\s]{1,25}\??$", re.I),
        re.compile(r"\b(?:nedir|ne demektir|tanımı|anlamı nedir)\b", re.I),
    ]

    _AGGREGATION_PATTERNS = [
        re.compile(r"\b(?:total|sum|average|avg|median|minimum|maximum|aggregate)\b", re.I),
        re.compile(r"\b(?:إجمالي|مجموع|متوسط|معدل|أعلى|أدنى)\b", re.I),
        re.compile(r"\b(?:toplam|ortalama|en yüksek|en düşük)\b", re.I),
    ]

    _MULTI_PART_PATTERNS = [
        re.compile(r"\b(?:and how did|and what was|as well as|in addition to)\b", re.I),
        re.compile(r"\b(?:وكيف|وما هو|بالإضافة إلى|وكذلك)\b", re.I),
        re.compile(r"\b(?:ve nasıl|ve ne kadar|bunun yanında|ayrıca)\b", re.I),
    ]

    def classify(self, query: str) -> tuple[QueryIntent, float]:
        """Classify query into a high-confidence enterprise search intent."""
        if not query or not query.strip():
            return QueryIntent.UNKNOWN, 0.0

        text = query.strip()

        # Multi-part check
        for pat in self._MULTI_PART_PATTERNS:
            if pat.search(text):
                return QueryIntent.MULTI_PART, 0.90

        # Comparison check
        for pat in self._COMPARISON_PATTERNS:
            if pat.search(text):
                return QueryIntent.COMPARISON, 0.95

        # Explanation check
        for pat in self._EXPLANATION_PATTERNS:
            if pat.search(text):
                return QueryIntent.EXPLANATION, 0.95

        # Summarization check
        for pat in self._SUMMARIZATION_PATTERNS:
            if pat.search(text):
                return QueryIntent.SUMMARIZATION, 0.95

        # Trend check
        for pat in self._TREND_PATTERNS:
            if pat.search(text):
                return QueryIntent.TREND_ANALYSIS, 0.90

        # Definition check
        for pat in self._DEFINITION_PATTERNS:
            if pat.search(text):
                return QueryIntent.DEFINITION, 0.90

        # Aggregation check
        for pat in self._AGGREGATION_PATTERNS:
            if pat.search(text):
                return QueryIntent.AGGREGATION, 0.85

        # Default factual lookup if it has keywords or question words
        return QueryIntent.FACTUAL_LOOKUP, 0.80
