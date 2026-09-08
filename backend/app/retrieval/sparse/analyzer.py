"""Multilingual lexical analyzer supporting Arabic, Turkish, English, and business tokens."""

import re
import unicodedata
import zlib
from collections import Counter

from app.retrieval.config import BM25Config
from app.retrieval.sparse.models import AnalyzedText

# Regex matching tokens:
# 1. Alphanumeric words with internal hyphens or underscores or dots, e.g. "XJ-4927", "v1.2", "Q4"
# 2. Percentage expressions, e.g. "15%"
# 3. Unicode letters and numbers across Arabic, Turkish, Latin, etc.
TOKEN_PATTERN = re.compile(r"[\w]+(?:[-_/\.][\w]+)*%?", re.UNICODE)

# Arabic Tashkeel (diacritics) regex
ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u064B-\u065F\u0670]")

# Arabic-Indic to ASCII digit translation table
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def turkish_lower(text: str) -> str:
    """Perform locale-accurate lowercasing for Turkish text.

    Correctly handles:
    - 'İ' (U+0130, capital I with dot) -> 'i' (U+0069, small i)
    - 'I' (U+0049, capital I without dot) -> 'ı' (U+0131, small dotless i)
    - Preserves and lowercases 'Ş' -> 'ş', 'Ğ' -> 'ğ', 'Ç' -> 'ç', 'Ö' -> 'ö', 'Ü' -> 'ü'
    """
    chars: list[str] = []
    for ch in text:
        if ch == "İ":
            chars.append("i")
        elif ch == "I":
            chars.append("ı")
        else:
            chars.append(ch.lower())
    return "".join(chars)


def normalize_arabic(text: str, strip_diacritics: bool = True) -> str:
    """Normalize Arabic text for deterministic lexical matching.

    Standardizes:
    - Normalizes Hamza forms: 'أ', 'إ', 'آ' -> 'ا'
    - Normalizes Taa Marbuta: 'ة' -> 'ه'
    - Normalizes Alef Maksura: 'ى' -> 'ي'
    - Strips Tashkeel diacritics if strip_diacritics is True
    - Converts Arabic-Indic digits to ASCII standard digits
    """
    if strip_diacritics:
        text = ARABIC_DIACRITICS_PATTERN.sub("", text)

    # Normalize letter shapes
    text = text.translate(str.maketrans("أإآةى", "اااهي"))

    # Normalize Eastern Arabic digits (٠-٩) to Western Arabic (0-9)
    text = text.translate(ARABIC_INDIC_DIGITS)

    return text


def compute_token_id(token: str, version: str = "bm25-v1") -> int:
    """Deterministically hash a token string to a stable positive 32-bit unsigned integer ID.

    Uses CRC32 with version prefixing:
    - Guaranteed deterministic across all OS architectures and Python processes.
    - Guarantees version isolation: tokens analyzed under 'bm25-v1' cannot mix with 'bm25-v2'.
    - Output is strictly within [1, 2^31 - 1] (positive non-zero int).
    """
    payload = f"{version}:{token}".encode()
    # Mask to 31-bit positive integer (1 to 2147483647)
    val = zlib.crc32(payload) & 0x7FFFFFFF
    return val if val != 0 else 1


class MultilingualSparseAnalyzer:
    """Enterprise-grade multilingual tokenizer and lexical analyzer.

    Supports:
    - Turkish linguistic casing (İ -> i, I -> ı).
    - Arabic normalization and optional Tashkeel stripping.
    - English and Latin tokenization.
    - Preservation of business identifiers, serial codes, percentages,
      and numbers (e.g. Q4, 2025, XJ-4927).
    - Deterministic token hashing to versioned integer IDs for sparse vector representation.
    """

    def __init__(self, config: BM25Config | None = None) -> None:
        self.config = config or BM25Config()

    def normalize(self, text: str) -> str:
        """Apply Unicode NFC normalization, Turkish casing, and Arabic letter standardization."""
        # 1. Unicode NFC normalization
        normalized = unicodedata.normalize("NFC", text)

        # 2. Turkish locale-aware lowercasing
        normalized = turkish_lower(normalized)

        # 3. Arabic standardization
        normalized = normalize_arabic(
            normalized,
            strip_diacritics=self.config.strip_arabic_diacritics,
        )

        return normalized

    def tokenize(self, text: str) -> list[str]:
        """Extract lexical tokens from input text using the multilingual pattern."""
        normalized = self.normalize(text)
        tokens = TOKEN_PATTERN.findall(normalized)
        # Strip residual leading/trailing punctuation from individual tokens if any
        cleaned_tokens: list[str] = []
        for t in tokens:
            cleaned = t.strip("-_/.")
            if cleaned:
                cleaned_tokens.append(cleaned)
        return cleaned_tokens

    def analyze(self, text: str) -> AnalyzedText:
        """Analyze text, computing token list, term frequencies, and deterministic token IDs."""

        tokens = self.tokenize(text)
        doc_len = len(tokens)

        # Count frequencies
        counter = Counter(tokens)

        term_frequencies: dict[int, int] = {}
        term_id_to_token: dict[int, str] = {}

        for tok, freq in counter.items():
            tok_id = compute_token_id(tok, version=self.config.version)
            term_frequencies[tok_id] = freq
            term_id_to_token[tok_id] = tok

        return AnalyzedText(
            raw_text=text,
            tokens=tokens,
            term_frequencies=term_frequencies,
            term_id_to_token=term_id_to_token,
            doc_len=doc_len,
        )
