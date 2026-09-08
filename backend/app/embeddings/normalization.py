"""Text and vector normalization utilities."""

import math
import re
import unicodedata
from collections.abc import Sequence

from app.embeddings.exceptions import EmbeddingInvalidInputError

# Regex to collapse multiple whitespace characters while preserving newlines
_MULTIPLE_SPACES = re.compile(r"[ \t]+")
_MULTIPLE_NEWLINES = re.compile(r"\n{3,}")


def normalize_embedding_text(text: str) -> str:
    """Normalize input text for embedding model consumption.

    Applies:
    - Unicode NFKC normalization (preserves Arabic, Turkish, English semantics).
    - Windows CRLF and CR normalization to standard LF (\n).
    - Collapsing redundant horizontal spaces while preserving necessary line breaks.
    - Stripping leading and trailing whitespace.

    Raises:
        EmbeddingInvalidInputError: If text is empty or purely whitespace.
    """
    if not isinstance(text, str):
        raise EmbeddingInvalidInputError("Embedding input text must be a string.")

    if not text or not text.strip():
        raise EmbeddingInvalidInputError(
            "Embedding input text cannot be empty or purely whitespace."
        )

    # 1. Unicode NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)

    # 2. Line ending normalization
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Horizontal whitespace collapse
    lines = [_MULTIPLE_SPACES.sub(" ", line).strip() for line in normalized.split("\n")]
    # Reassemble and collapse 3+ consecutive newlines to 2
    reassembled = "\n".join(lines)
    reassembled = _MULTIPLE_NEWLINES.sub("\n\n", reassembled).strip()

    if not reassembled:
        raise EmbeddingInvalidInputError("Embedding input text is empty after normalization.")

    return reassembled


def l2_normalize_vector(vector: Sequence[float], eps: float = 1e-12) -> list[float]:
    """Perform L2 (Euclidean) normalization on a vector: v -> v / ||v||.

    If norm is smaller than eps, returns the original vector to avoid zero division.
    """
    norm_sq = sum(x * x for x in vector)
    norm = math.sqrt(norm_sq)
    if norm < eps:
        return list(vector)
    return [float(x / norm) for x in vector]
