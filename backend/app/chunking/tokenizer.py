"""Token counting and tokenization abstractions for multilingual text.

Supports Arabic, Turkish, English, and mixed-script text without external LLM dependencies.
Handles Unicode normalization, Arabic diacritics, and agglutinative/accented tokens.
"""

import re
import unicodedata
from abc import ABC, abstractmethod


class TokenCounter(ABC):
    """Abstract interface for counting and splitting text into tokens."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count the estimated number of tokens in the given text."""
        ...

    @abstractmethod
    def split_into_tokens(self, text: str) -> list[str]:
        """Split text into individual token fragments."""
        ...

    @abstractmethod
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to at most max_tokens without breaking words."""
        ...


class MultilingualTokenCounter(TokenCounter):
    """Multilingual, deterministic token counter and boundary analyzer.

    Uses Unicode-aware regex patterns designed to handle:
    - Latin scripts (English, Turkish with ç, ğ, ı, ö, ş, ü, İ)
    - Arabic script (including letters, hamzas, and diacritics / tashkeel \u064b-\u065f)
    - Numbers, punctuation, whitespace, and alphanumeric tokens
    """

    # Regex matching:
    # 1. Arabic word cluster: letters optionally followed by diacritics / tashkeel
    # 2. Latin / general word cluster: \w+ (including unicode word characters)
    # 3. Numeric tokens: integer or decimal
    # 4. Punctuation or special symbols (non-whitespace)
    _TOKEN_PATTERN = re.compile(
        r"[\u0621-\u064A\u0660-\u0669\u0671-\u06D3\u064B-\u065F\u0670]+"  # Arabic word token
        r"|[^\W\d_]+"  # Any Unicode alphabetic word (Latin/Turkish/etc.)
        r"|\d+(?:[.,]\d+)?"  # Numbers (integers or decimals)
        r"|[^\w\s]"  # Punctuation / symbols
        r"|\s+",  # Whitespace sequences
        re.UNICODE,
    )

    # Simplified token pattern for fast counting (ignoring pure whitespace)
    _CONTENT_TOKEN_PATTERN = re.compile(
        r"[\u0621-\u064A\u0660-\u0669\u0671-\u06D3\u064B-\u065F\u0670]+"
        r"|[^\W\d_]+"
        r"|\d+(?:[.,]\d+)?"
        r"|[^\w\s]",
        re.UNICODE,
    )

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Returns 0 for empty or whitespace-only text.
        For non-empty text, counts lexical and structural tokens.
        In agglutinative or morphological scripts, words longer than 8 characters
        are approximated as multiple subword tokens (~1.3x) to match standard BPE tokenizers.
        """
        if not text or not text.strip():
            return 0

        # Normalize unicode to NFKC
        normalized = unicodedata.normalize("NFKC", text)
        matches = self._CONTENT_TOKEN_PATTERN.findall(normalized)

        total_tokens = 0
        for token in matches:
            total_tokens += 1
            length = len(token)
            # Standard subword approximation for long composite tokens
            if length > 8:
                total_tokens += (length - 8) // 4

        return total_tokens

    def split_into_tokens(self, text: str) -> list[str]:
        """Split text into raw token fragments preserving spaces and punctuation."""
        if not text:
            return []
        normalized = unicodedata.normalize("NFKC", text)
        return self._TOKEN_PATTERN.findall(normalized)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to at most max_tokens without breaking words."""
        if not text or max_tokens <= 0:
            return ""

        tokens = self.split_into_tokens(text)
        accumulated: list[str] = []
        current_token_count = 0

        for tok in tokens:
            if not tok.isspace():
                tok_len = len(tok)
                sub_count = 1 + ((tok_len - 8) // 4 if tok_len > 8 else 0)
            else:
                sub_count = 0

            if current_token_count + sub_count > max_tokens:
                break

            accumulated.append(tok)
            current_token_count += sub_count

        return "".join(accumulated).rstrip()


# Global default tokenizer instance
default_token_counter = MultilingualTokenCounter()
