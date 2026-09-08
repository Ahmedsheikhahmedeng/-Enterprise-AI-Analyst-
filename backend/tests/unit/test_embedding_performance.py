"""Performance benchmarks and throughput tests for embedding pipeline."""

import time
import uuid

import pytest

from app.embeddings import (
    EmbeddingConfig,
    EmbeddingService,
    InMemoryEmbeddingCache,
    LocalDeterministicEmbeddingProvider,
)


@pytest.mark.asyncio
async def test_embedding_throughput_and_cache_performance() -> None:
    """Benchmark chunks/sec throughput, average batch latency, and cache speedup."""
    config = EmbeddingConfig(
        provider="local",
        model="local-benchmark-model",
        dimensions=1536,
        batch_size=64,
        max_input_tokens=8191,
        timeout_seconds=30.0,
        max_retries=1,
        retry_backoff_factor=1.0,
        normalize=True,
        cache_enabled=True,
        cache_ttl_seconds=3600,
        max_concurrent_requests=8,
        api_key=None,
        api_base_url=None,
        version="1.0.0",
    )
    provider = LocalDeterministicEmbeddingProvider(dimensions=1536)
    cache = InMemoryEmbeddingCache()
    service = EmbeddingService(config=config, provider=provider, cache=cache)

    total_chunks = 200
    chunks = [
        {
            "id": uuid.uuid4(),
            "content": f"Financial analysis segment #{i} with operational revenue and cost data.",
            "heading_context": f"Section {i // 10}",
        }
        for i in range(total_chunks)
    ]

    # Cold run (no cache)
    t0 = time.perf_counter()
    cold_result = await service.embed_chunks(chunks)
    cold_duration = time.perf_counter() - t0

    assert cold_result.status == "success"
    assert cold_result.success_count == total_chunks
    cold_throughput = total_chunks / cold_duration

    # Warm run (full cache hits)
    t1 = time.perf_counter()
    warm_result = await service.embed_chunks(chunks)
    warm_duration = time.perf_counter() - t1

    assert warm_result.status == "success"
    assert warm_result.metrics is not None
    assert warm_result.metrics.cache_hits == total_chunks
    warm_throughput = total_chunks / warm_duration

    # Performance assertions
    assert cold_throughput > 100.0, f"Cold throughput too low: {cold_throughput:.1f} chunks/sec"
    assert warm_throughput > 500.0, f"Warm throughput too low: {warm_throughput:.1f} chunks/sec"
    assert warm_duration < cold_duration, "Cached run should be faster than cold run"
