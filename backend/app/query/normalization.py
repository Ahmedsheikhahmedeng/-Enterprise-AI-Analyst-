"""Deterministic, multilingual-safe query normalization."""

import re
import unicodedata


class QueryNormalizer:
    """Normalizes natural language queries without corrupting business codes or identifiers."""

    _WHITESPACE_RE = re.compile(r"[\s\u200b\u200c\u200d\uFEFF]+")
    _CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    _EXCESSIVE_PUNCT_RE = re.compile(r"([!?.,;:])\1+")

    def normalize(self, query: str) -> str:
        """Perform safe normalization on query string.

        Preserves:
        - Numbers, currency ($120M, €50K), percentages (15.5%)
        - Business codes and identifiers (e.g. XJ-4927, SKU-102)
        - Fiscal quarters and dates (Q4 2025, 2024-10-12)
        - Multilingual characters across Arabic, Turkish, and Latin alphabets
        """
        if not query:
            return ""

        # 1. Unicode NFC standard normalization
        text = unicodedata.normalize("NFC", query)

        # 2. Strip control characters
        text = self._CONTROL_CHARS_RE.sub("", text)

        # 3. Collapse repeated excessive punctuation (e.g. "????" -> "?")
        text = self._EXCESSIVE_PUNCT_RE.sub(r"\1", text)

        # 4. Collapse multiple whitespace and zero-width spaces into single space
        text = self._WHITESPACE_RE.sub(" ", text).strip()

        return text
