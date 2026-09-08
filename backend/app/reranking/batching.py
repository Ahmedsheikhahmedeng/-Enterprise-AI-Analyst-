"""Batching utilities for cross-encoder pair inference."""

from collections.abc import Sequence

from app.reranking.exceptions import RerankerInputError


def create_batches[T](items: Sequence[T], batch_size: int) -> list[list[T]]:
    """Partition a sequence of items into contiguous batches of specified size.

    Args:
        items: Sequence of items to partition.
        batch_size: Positive integer specifying maximum items per batch.

    Returns:
        List of batches, where each batch is a list of items.

    Raises:
        RerankerInputError: If batch_size < 1.
    """
    if batch_size < 1:
        raise RerankerInputError(
            f"Batch size must be greater than or equal to 1, received {batch_size}."
        )

    if not items:
        return []

    return [list(items[i : i + batch_size]) for i in range(0, len(items), batch_size)]
