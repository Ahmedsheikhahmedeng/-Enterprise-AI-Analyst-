"""Vector shape and numerical integrity validators."""

import math
from collections.abc import Sequence

from app.embeddings.exceptions import (
    EmbeddingDimensionError,
    EmbeddingValidationError,
)


def validate_embedding_vector(
    vector: Sequence[float],
    expected_dimensions: int,
) -> None:
    """Validate that an embedding vector meets all numerical and dimensional invariants.

    Checks:
    - Not None, not empty
    - Correct dimensional length
    - All elements are finite real numbers (no NaN, +inf, -inf)
    """
    if vector is None:
        raise EmbeddingValidationError("Embedding vector is None.")

    actual_len = len(vector)
    if actual_len == 0:
        raise EmbeddingValidationError("Embedding vector is empty.")

    if actual_len != expected_dimensions:
        raise EmbeddingDimensionError(
            expected=expected_dimensions,
            actual=actual_len,
            message=(
                f"Embedding vector dimension mismatch: expected {expected_dimensions}, "
                f"but provider returned {actual_len} dimensions."
            ),
        )

    for idx, val in enumerate(vector):
        if not isinstance(val, (int, float)):
            raise EmbeddingValidationError(
                f"Non-numeric value detected at vector index {idx}: type {type(val).__name__}."
            )
        if not math.isfinite(val):
            raise EmbeddingValidationError(
                f"Non-finite numeric value (NaN or Infinity) detected at vector index {idx}: {val}."
            )
