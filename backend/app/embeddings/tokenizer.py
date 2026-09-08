"""Tokenization and token counting abstractions for embedding models."""

import re
from typing import Protocol, runtime_checkable

from app.embeddings.exceptions import EmbeddingInvalidInputError

# Regex token pattern splitting on whitespace, words, and unicode punctuation
_TOKEN_PATTERN = re.compile(
    r"\w+|[^\w\s]",
    re.UNICODE,
)


@runtime_checkable
class EmbeddingTokenizer(Protocol):
    """Protocol for embedding tokenizers."""

    def count_tokens(self, text: str) -> int:
        """Calculate the estimated token count for the given text."""
        ...

    def validate_limit(self, text: str, max_tokens: int) -> int:
        """Validate that text does not exceed max_tokens, returning token count."""
        ...


class UniversalEmbeddingTokenizer:
    """Universal token counter supporting multilingual text (Arabic, Turkish, English, etc.).

    Uses tiktoken if installed and matching model family, otherwise uses a calibrated
    multilingual token estimation based on Unicode character-to-subword expansion.
    Does NOT perform silent truncation.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or "text-embedding-3-small"
        self._tiktoken_encoding = None
        try:
            import tiktoken  # type: ignore

            try:
                self._tiktoken_encoding = tiktoken.encoding_for_model(self.model_name)
            except Exception:
                self._tiktoken_encoding = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            self._tiktoken_encoding = None

    def count_tokens(self, text: str) -> int:
        """Count tokens for text without mutating or truncating."""
        if not text:
            return 0

        if self._tiktoken_encoding is not None:
            return len(self._tiktoken_encoding.encode(text, disallowed_special=()))

        # High-accuracy fallback:
        # Matches word tokens and punctuation boundaries, accounting for subword splitting.
        tokens = _TOKEN_PATTERN.findall(text)
        total_tokens = 0
        for token in tokens:
            # Short ASCII/Latin words are typically 1 token.
            # Longer words or non-ASCII scripts (Arabic, Turkish accents, etc.)
            # split into multiple BPE subwords (approx ~3.5 chars per token).
            length = len(token)
            if length <= 4:
                total_tokens += 1
            else:
                total_tokens += max(1, (length + 2) // 3)

        return max(1, total_tokens)

    def validate_limit(self, text: str, max_tokens: int) -> int:
        """Count tokens and ensure it does not exceed the limit.

        Raises:
            EmbeddingInvalidInputError: If token count exceeds max_tokens.
        """
        token_count = self.count_tokens(text)
        if token_count > max_tokens:
            raise EmbeddingInvalidInputError(
                f"Embedding input exceeded max token limit: {token_count} tokens > "
                f"limit of {max_tokens}. Silent truncation is forbidden. "
                "Please re-chunk or adjust the input."
            )

        return token_count
