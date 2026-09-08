"""Lightweight, deterministic multilingual language detection."""

import re

from app.query.models import LanguageDetectionResult


class LanguageDetector:
    """Detects Arabic, Turkish, English, and mixed language queries."""

    # Unicode ranges
    _ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
    _TURKISH_SPECIFIC_RE = re.compile(r"[çÇğĞıİöÖşŞüÜ]")

    # High-frequency language stop/cue words
    _ARABIC_WORDS = {
        "ما",
        "هو",
        "هي",
        "سبب",
        "انخفاض",
        "ارتفاع",
        "هامش",
        "التشغيل",
        "الإيرادات",
        "الارباح",
        "تقرير",
        "مقارنة",
        "في",
        "من",
        "عن",
        "على",
        "إلى",
        "كم",
        "كيف",
        "لماذا",
        "صافي",
        "الربع",
    }
    _TURKISH_WORDS = {
        "neden",
        "neydi",
        "nasil",
        "nasıl",
        "gelir",
        "faaliyet",
        "marjı",
        "marji",
        "düşüşün",
        "dususun",
        "artis",
        "artış",
        "kar",
        "kâr",
        "raporu",
        "karsilastir",
        "karşılaştır",
        "özetle",
        "ve",
        "ile",
        "için",
        "icin",
        "bir",
        "bu",
        "dönem",
        "donem",
        "çeyrek",
        "ceyrek",
    }
    _ENGLISH_WORDS = {
        "what",
        "why",
        "how",
        "when",
        "where",
        "revenue",
        "operating",
        "margin",
        "decline",
        "increase",
        "profit",
        "loss",
        "compare",
        "comparison",
        "summarize",
        "summary",
        "report",
        "quarter",
        "fiscal",
        "year",
        "and",
        "in",
        "of",
        "the",
        "for",
        "to",
        "with",
        "was",
        "did",
        "is",
    }

    def detect(self, query: str) -> LanguageDetectionResult:
        """Detect primary and secondary languages present in query text."""
        if not query or not query.strip():
            return LanguageDetectionResult(
                primary_language="unknown", detected_languages=[], confidence=0.0
            )

        text = query.lower().strip()
        words = re.findall(r"\b[\w'-]+\b", text)

        ar_char_count = len(self._ARABIC_RE.findall(query))
        tr_specific_char_count = len(self._TURKISH_SPECIFIC_RE.findall(query))

        ar_word_matches = sum(
            1 for w in words if w in self._ARABIC_WORDS or self._ARABIC_RE.search(w)
        )
        tr_word_matches = sum(
            1 for w in words if w in self._TURKISH_WORDS or self._TURKISH_SPECIFIC_RE.search(w)
        )
        en_word_matches = sum(1 for w in words if w in self._ENGLISH_WORDS)

        detected_langs: list[str] = []
        if ar_char_count > 0 or ar_word_matches > 0:
            detected_langs.append("ar")
        if tr_specific_char_count > 0 or tr_word_matches > 0:
            detected_langs.append("tr")
        if en_word_matches > 0:
            detected_langs.append("en")

        # Fallback character check if no cue words matched
        if not detected_langs:
            latin_count = sum(1 for c in text if "a" <= c <= "z")
            if latin_count > 0:
                detected_langs.append("en")
            else:
                return LanguageDetectionResult(
                    primary_language="unknown", detected_languages=[], confidence=0.5
                )

        # Multi-language / mixed detection
        if len(detected_langs) > 1:
            # Determine dominant language based on match counts
            counts = {
                "ar": ar_char_count * 2 + ar_word_matches * 3,
                "tr": tr_specific_char_count * 2 + tr_word_matches * 3,
                "en": en_word_matches * 2,
            }
            primary = max(detected_langs, key=lambda lang: counts.get(lang, 0))
            return LanguageDetectionResult(
                primary_language="mixed" if len(detected_langs) >= 2 else primary,
                detected_languages=detected_langs,
                confidence=0.85,
            )

        primary = detected_langs[0]
        confidence = 0.95 if (ar_word_matches + tr_word_matches + en_word_matches) > 0 else 0.80
        return LanguageDetectionResult(
            primary_language=primary,
            detected_languages=detected_langs,
            confidence=confidence,
        )
