"""Batching and concurrency control utilities for embedding generation."""

import asyncio
from collections.abc import Callable, Coroutine, Sequence


def create_batches[T](items: Sequence[T], batch_size: int) -> list[list[T]]:
    """Partition a sequence of items into consecutive chunks of size batch_size."""
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")
    return [list(items[i : i + batch_size]) for i in range(0, len(items), batch_size)]


async def process_batches_with_concurrency[T, R](
    batches: list[list[T]],
    process_fn: Callable[[int, list[T]], Coroutine[None, None, list[R]]],
    max_concurrency: int = 5,
) -> list[R]:
    """Execute batch processing with an asyncio Semaphore to throttle concurrent requests.

    Guarantees:
    - Results strictly maintain the original sequence order regardless of completion order.
    """
    if not batches:
        return []

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _worker(batch_idx: int, batch: list[T]) -> tuple[int, list[R]]:
        async with semaphore:
            result = await process_fn(batch_idx, batch)
            return batch_idx, result

    tasks = [_worker(i, batch) for i, batch in enumerate(batches)]
    batch_results = await asyncio.gather(*tasks)

    # Sort results by batch_idx to strictly preserve input order
    batch_results.sort(key=lambda x: x[0])

    flattened: list[R] = []
    for _, res_list in batch_results:
        flattened.extend(res_list)

    return flattened
