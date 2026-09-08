"""Multilingual Semantic Text Normalizer supporting Arabic, Turkish, and English."""

import re
import unicodedata

# Arabic regex patterns
ARABIC_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u065F\u0670]")
ARABIC_TATWEEL = re.compile(r"\u0640")
ARABIC_ALEF_VARIANTS = re.compile(r"[\u0622\u0623\u0625\u0671]")
ARABIC_TEH_MARBUTA = re.compile(r"\u0629")
ARABIC_ALEF_MAKSURA = re.compile(r"\u0649")

# Punctuation & Whitespace
PUNCTUATION_PATTERN = re.compile(r"[^\w\s\u0600-\u06FF]")
WHITESPACE_PATTERN = re.compile(r"\s+")


class SemanticTextNormalizer:
    """Normalizes natural language expressions across Arabic, Turkish, and English."""

    @classmethod
    def normalize(cls, text: str, preserve_punctuation: bool = False) -> str:
        """Clean and canonicalize multilingual text into a normalized search key."""
        if not text:
            return ""

        # 1. Unicode NFKC Normalization
        normalized = unicodedata.normalize("NFKC", text)

        # 2. Turkish custom lowercasing (handle dotted / dotless I)
        normalized = normalized.replace("İ", "i").replace("I", "ı").lower()

        # 3. Arabic Normalization
        # Remove diacritics (harakat)
        normalized = ARABIC_DIACRITICS.sub("", normalized)
        # Remove tatweel (kashida)
        normalized = ARABIC_TATWEEL.sub("", normalized)
        # Normalize alef variants to bare alef
        normalized = ARABIC_ALEF_VARIANTS.sub("\u0627", normalized)
        # Normalize teh marbuta to heh
        normalized = ARABIC_TEH_MARBUTA.sub("\u0647", normalized)
        # Normalize alef maksura to yeh
        normalized = ARABIC_ALEF_MAKSURA.sub("\u064a", normalized)

        # 4. Remove punctuation if required
        if not preserve_punctuation:
            normalized = PUNCTUATION_PATTERN.sub(" ", normalized)

        # 5. Collapse Whitespace and strip
        normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()

        return normalized

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Heuristic language detection between Arabic, Turkish, and English."""
        if not text:
            return "en"

        arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
        turkish_chars = sum(1 for c in text if c in "çğıöşüÇĞİÖŞÜ")

        total_letters = sum(1 for c in text if c.isalpha())
        if total_letters == 0:
            return "en"

        if arabic_chars / total_letters > 0.3:
            return "ar"
        if turkish_chars / total_letters > 0.05:
            return "tr"
        return "en"
