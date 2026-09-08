"""Comprehensive unit tests for the embeddings subsystem."""

import asyncio
import math
import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.embeddings import (
    EmbeddingConfig,
    EmbeddingDimensionError,
    EmbeddingInvalidInputError,
    EmbeddingPricing,
    EmbeddingProviderFactory,
    EmbeddingService,
    EmbeddingTextBuilder,
    EmbeddingValidationError,
    InMemoryEmbeddingCache,
    LocalDeterministicEmbeddingProvider,
    OpenAIEmbeddingProvider,
    UniversalEmbeddingTokenizer,
    build_embedding_cache_key,
    compute_embedding_input_hash,
    create_batches,
    l2_normalize_vector,
    normalize_embedding_text,
    process_batches_with_concurrency,
    validate_embedding_vector,
)
from app.embeddings.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingConfigurationError,
)

# ==========================================
# 1. Normalization & Text Preparation Tests
# ==========================================


def test_normalize_embedding_text_arabic_turkish_english() -> None:
    """Multilingual text normalization must preserve characters without corruption."""
    arabic = "تحليل أداء الشركة خلال الربع الرابع من عام 2025"
    norm_ar = normalize_embedding_text(arabic)
    assert norm_ar == arabic

    turkish = "Şirketin 2025 yılı dördüncü çeyrek performans analizi"
    norm_tr = normalize_embedding_text(turkish)
    assert norm_tr == turkish
    assert "ı" in norm_tr and "ç" in norm_tr and "Ş" in norm_tr

    mixed = "2025 Revenue Analysis — تحليل الإيرادات — Gelir Analizi"
    norm_mix = normalize_embedding_text(mixed)
    assert norm_mix == mixed

    # Whitespace and CRLF collapse
    messy = "  Line 1   with   spaces\r\n\r\n\r\n\r\nLine 2   \t  "
    clean = normalize_embedding_text(messy)
    assert clean == "Line 1 with spaces\n\nLine 2"


def test_normalize_embedding_text_empty_fails() -> None:
    """Empty or whitespace-only inputs must raise EmbeddingInvalidInputError."""
    with pytest.raises(EmbeddingInvalidInputError):
        normalize_embedding_text("")
    with pytest.raises(EmbeddingInvalidInputError):
        normalize_embedding_text("   \n\t  ")


def test_embedding_text_builder_immutability() -> None:
    """EmbeddingTextBuilder combines heading context with content and leaves chunk immutable."""

    class MockChunk:
        def __init__(self, content: str, heading_context: str | None = None) -> None:
            self.id = uuid.uuid4()
            self.content = content
            self.heading_context = heading_context

    original_content = "Revenue increased by 15% in 2025."
    chunk = MockChunk(
        content=original_content,
        heading_context="Financial Performance > Revenue",
    )

    result = EmbeddingTextBuilder.build_from_chunk(chunk)
    expected = "Financial Performance > Revenue\n\nRevenue increased by 15% in 2025."
    assert result == expected
    # Ensure source content is completely immutable
    assert chunk.content == original_content


def test_embedding_text_builder_no_technical_metadata() -> None:
    """Technical database IDs must not be included in embedding text."""
    chunk = {
        "id": uuid.uuid4(),
        "organization_id": uuid.uuid4(),
        "content": "Core analysis paragraph.",
        "heading_context": "Section 1",
    }
    result = EmbeddingTextBuilder.build_from_chunk(chunk)
    assert result == "Section 1\n\nCore analysis paragraph."
    assert str(chunk["id"]) not in result
    assert str(chunk["organization_id"]) not in result


# ==========================================
# 2. Tokenizer & Token Limits Tests
# ==========================================


def test_tokenizer_counting_and_limits() -> None:
    """Tokenizer estimates tokens and rejects text exceeding limits with no silent truncation."""
    tokenizer = UniversalEmbeddingTokenizer()

    count_en = tokenizer.count_tokens("This is a simple sentence.")
    assert count_en > 0

    count_ar = tokenizer.count_tokens("تحليل أداء الشركة المالي")
    assert count_ar > 0

    # Within limit
    val = tokenizer.validate_limit("Short text", max_tokens=100)
    assert val > 0

    # Exceeding limit must raise error
    with pytest.raises(EmbeddingInvalidInputError) as exc_info:
        tokenizer.validate_limit(
            "This is a longer sentence that will exceed our tiny threshold",
            max_tokens=3,
        )
    assert "exceeded max token limit" in str(exc_info.value)
    assert "Silent truncation is forbidden" in str(exc_info.value)


# ==========================================
# 3. Vector Validation & L2 Normalization Tests
# ==========================================


def test_validate_embedding_vector_dimensions() -> None:
    """Vector dimension mismatch must raise EmbeddingDimensionError."""
    correct_vec = [0.1] * 1536
    validate_embedding_vector(correct_vec, expected_dimensions=1536)

    wrong_vec = [0.1] * 1535
    with pytest.raises(EmbeddingDimensionError) as exc_info:
        validate_embedding_vector(wrong_vec, expected_dimensions=1536)
    assert exc_info.value.expected == 1536
    assert exc_info.value.actual == 1535


def test_validate_embedding_vector_numerics() -> None:
    """Non-finite floats (NaN, Inf) or empty vectors must fail validation."""
    with pytest.raises(EmbeddingValidationError):
        validate_embedding_vector([], expected_dimensions=0)

    nan_vec = [0.1, float("nan"), 0.3]
    with pytest.raises(EmbeddingValidationError) as exc:
        validate_embedding_vector(nan_vec, expected_dimensions=3)
    assert "NaN or Infinity" in str(exc.value)

    inf_vec = [0.1, float("inf"), 0.3]
    with pytest.raises(EmbeddingValidationError):
        validate_embedding_vector(inf_vec, expected_dimensions=3)


def test_l2_normalize_vector() -> None:
    """L2 normalization produces unit vectors with Euclidean norm of 1.0."""
    raw_vec = [3.0, 4.0]
    norm_vec = l2_normalize_vector(raw_vec)
    assert math.isclose(norm_vec[0], 0.6, abs_tol=1e-6)
    assert math.isclose(norm_vec[1], 0.8, abs_tol=1e-6)
    norm = math.sqrt(sum(x * x for x in norm_vec))
    assert math.isclose(norm, 1.0, abs_tol=1e-6)

    # Zero vector handling
    zero_vec = [0.0, 0.0]
    assert l2_normalize_vector(zero_vec) == [0.0, 0.0]


# ==========================================
# 4. Deterministic Identity & Hash Tests
# ==========================================


def test_deterministic_embedding_input_hash() -> None:
    """Input text and configuration parameters produce deterministic SHA-256 hashes."""
    h1 = compute_embedding_input_hash(
        normalized_text="Sample text",
        provider="openai",
        model="text-embedding-3-small",
        version="1.0.0",
        dimensions=1536,
        normalization_mode="l2",
    )
    h2 = compute_embedding_input_hash(
        normalized_text="Sample text",
        provider="openai",
        model="text-embedding-3-small",
        version="1.0.0",
        dimensions=1536,
        normalization_mode="l2",
    )
    assert h1 == h2
    assert len(h1) == 64

    # Any parameter change must yield a different hash
    h_diff_model = compute_embedding_input_hash(
        normalized_text="Sample text",
        provider="openai",
        model="text-embedding-3-large",
        version="1.0.0",
        dimensions=1536,
        normalization_mode="l2",
    )
    assert h1 != h_diff_model


# ==========================================
# 5. Local Deterministic Provider Tests
# ==========================================


@pytest.mark.asyncio
async def test_local_deterministic_provider() -> None:
    """Local provider generates deterministic, normalized unit vectors without external calls."""
    provider = LocalDeterministicEmbeddingProvider(dimensions=512)
    assert provider.provider_name == "local"
    assert provider.dimensions == 512
    assert await provider.health_check() is True

    texts = ["First chunk text", "Second chunk text", "Third chunk text"]
    resp = await provider.embed_texts(texts)

    assert len(resp.vectors) == 3
    for v in resp.vectors:
        assert len(v) == 512
        norm = math.sqrt(sum(x * x for x in v))
        assert math.isclose(norm, 1.0, abs_tol=1e-5)

    # Identical texts must yield identical vectors
    resp2 = await provider.embed_texts(["First chunk text"])
    assert resp.vectors[0] == resp2.vectors[0]


# ==========================================
# 6. Provider Factory Tests
# ==========================================


def test_provider_factory_supported_and_unsupported() -> None:
    """Factory instantiates valid providers and rejects unknown providers safely."""
    cfg_local = EmbeddingConfig(
        provider="local",
        model="local-model",
        dimensions=768,
        batch_size=32,
        max_input_tokens=8191,
        timeout_seconds=30.0,
        max_retries=3,
        retry_backoff_factor=1.5,
        normalize=True,
        cache_enabled=False,
        cache_ttl_seconds=3600,
        max_concurrent_requests=5,
        api_key=None,
        api_base_url=None,
        version="1.0.0",
    )
    p_local = EmbeddingProviderFactory.create(cfg_local)
    assert isinstance(p_local, LocalDeterministicEmbeddingProvider)

    cfg_bad = EmbeddingConfig(
        provider="nonexistent-provider",
        model="xyz",
        dimensions=768,
        batch_size=32,
        max_input_tokens=8191,
        timeout_seconds=30.0,
        max_retries=3,
        retry_backoff_factor=1.5,
        normalize=True,
        cache_enabled=False,
        cache_ttl_seconds=3600,
        max_concurrent_requests=5,
        api_key=None,
        api_base_url=None,
        version="1.0.0",
    )
    with pytest.raises(EmbeddingConfigurationError) as exc_info:
        EmbeddingProviderFactory.create(cfg_bad)
    assert "Unsupported embedding provider" in str(exc_info.value)


# ==========================================
# 7. OpenAI Provider Tests & Retries
# ==========================================


@pytest.mark.asyncio
async def test_openai_provider_success() -> None:
    """OpenAI provider parses response and preserves vector ordering based on index."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"index": 1, "embedding": [0.2] * 4},
            {"index": 0, "embedding": [0.1] * 4},
        ],
        "usage": {"prompt_tokens": 12, "total_tokens": 12},
    }
    mock_client.post.return_value = mock_response

    provider = OpenAIEmbeddingProvider(
        api_key="test-secret-key",
        dimensions=4,
        client=mock_client,
    )
    resp = await provider.embed_texts(["Text A", "Text B"])

    # Strict ordering: index 0 (0.1) then index 1 (0.2)
    assert len(resp.vectors) == 2
    assert resp.vectors[0] == [0.1] * 4
    assert resp.vectors[1] == [0.2] * 4
    assert resp.total_tokens == 12


@pytest.mark.asyncio
async def test_openai_provider_auth_error_no_retry() -> None:
    """401 Unauthorized must raise EmbeddingAuthenticationError without leaking secret."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Incorrect API key provided"
    mock_client.post.return_value = mock_response

    provider = OpenAIEmbeddingProvider(
        api_key="sk-secret-12345",
        client=mock_client,
        max_retries=3,
    )
    with pytest.raises(EmbeddingAuthenticationError) as exc:
        await provider.embed_texts(["Sample"])
    assert "Authentication failed" in str(exc.value)
    # Never leak secrets in error
    assert "sk-secret-12345" not in str(exc.value)
    # Only 1 attempt, no useless retries on 401
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_openai_provider_rate_limit_retry() -> None:
    """429 Rate limit must retry with backoff and succeed if subsequent attempt passes."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False

    res_429 = MagicMock()
    res_429.status_code = 429
    res_429.headers = {}

    res_200 = MagicMock()
    res_200.status_code = 200
    res_200.json.return_value = {
        "data": [{"index": 0, "embedding": [0.5] * 1536}],
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }

    mock_client.post.side_effect = [res_429, res_200]

    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        client=mock_client,
        max_retries=2,
        retry_backoff_factor=0.01,
    )
    resp = await provider.embed_texts(["Text"])
    assert len(resp.vectors) == 1
    assert mock_client.post.call_count == 2


# ==========================================
# 8. Batching & Concurrency Tests
# ==========================================


def test_create_batches() -> None:
    """Batch partitioning handles exact multiples, remainders, and single elements."""
    items = list(range(10))
    batches = create_batches(items, batch_size=3)
    assert batches == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]

    assert create_batches([], 5) == []


@pytest.mark.asyncio
async def test_process_batches_with_concurrency_ordering() -> None:
    """Concurrent batch execution must strictly preserve input ordering."""
    batches = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]

    async def mock_processor(batch_idx: int, batch: list[int]) -> list[int]:
        # Simulate variable network latencies
        await asyncio.sleep(0.01 * (3 - batch_idx))
        return [x * 10 for x in batch]

    results = await process_batches_with_concurrency(
        batches=batches,
        process_fn=mock_processor,
        max_concurrency=3,
    )
    # Order must be strictly 0, 10, 20, 30, 40, 50, 60, 70, 80
    assert results == [0, 10, 20, 30, 40, 50, 60, 70, 80]


# ==========================================
# 9. Cache Tests
# ==========================================


@pytest.mark.asyncio
async def test_cache_abstraction() -> None:
    """Cache handles set, get, get_many, set_many, and keys without raw text."""
    cache = InMemoryEmbeddingCache()
    key1 = build_embedding_cache_key("openai", "text-embedding-3-small", "1.0", "hash1")
    assert key1 == "embedding:openai:text-embedding-3-small:1.0:hash1"
    # Never contains raw text
    assert "raw" not in key1

    assert await cache.get(key1) is None
    vec = [0.1, 0.2, 0.3]
    await cache.set(key1, vec)
    assert await cache.get(key1) == vec

    # Batch operations
    key2 = build_embedding_cache_key("openai", "text-embedding-3-small", "1.0", "hash2")
    await cache.set_many([(key2, [0.4, 0.5, 0.6])])
    results = await cache.get_many([key1, key2, "missing_key"])
    assert results[0] == vec
    assert results[1] == [0.4, 0.5, 0.6]
    assert results[2] is None


# ==========================================
# 10. Pricing Tests
# ==========================================


def test_embedding_pricing() -> None:
    """Pricing calculates cost for known models and returns None for unknown."""
    cost_small = EmbeddingPricing.estimate_cost("text-embedding-3-small", total_tokens=1_000_000)
    assert cost_small == 0.02

    cost_large = EmbeddingPricing.estimate_cost("text-embedding-3-large", total_tokens=500_000)
    assert cost_large == 0.065

    cost_local = EmbeddingPricing.estimate_cost("custom-model", 10_000, provider="local")
    assert cost_local == 0.0

    cost_unknown = EmbeddingPricing.estimate_cost("unknown-model", total_tokens=10_000)
    assert cost_unknown is None


# ==========================================
# 11. Full EmbeddingService Integration Tests
# ==========================================


@pytest.mark.asyncio
async def test_embedding_service_end_to_end() -> None:
    """EmbeddingService orchestrates batching, caching, ordering, and observability."""
    config = EmbeddingConfig(
        provider="local",
        model="local-deterministic-v1",
        dimensions=128,
        batch_size=2,
        max_input_tokens=1000,
        timeout_seconds=10.0,
        max_retries=1,
        retry_backoff_factor=1.0,
        normalize=True,
        cache_enabled=True,
        cache_ttl_seconds=3600,
        max_concurrent_requests=2,
        api_key=None,
        api_base_url=None,
        version="1.0.0",
    )
    provider = LocalDeterministicEmbeddingProvider(dimensions=128)
    cache = InMemoryEmbeddingCache()
    service = EmbeddingService(config=config, provider=provider, cache=cache)

    chunks = [
        {"id": uuid.uuid4(), "content": "First chunk text", "heading_context": "Header 1"},
        {"id": uuid.uuid4(), "content": "Second chunk text", "heading_context": "Header 2"},
        {"id": uuid.uuid4(), "content": "Third chunk text", "heading_context": "Header 3"},
    ]

    # First execution (cache misses)
    res1 = await service.embed_chunks(chunks)
    assert res1.status == "success"
    assert res1.success_count == 3
    assert res1.failed_count == 0
    assert len(res1.items) == 3
    assert res1.metrics is not None
    assert res1.metrics.cache_hits == 0
    assert res1.metrics.cache_misses == 3
    for it in res1.items:
        assert it.vector is not None
        assert len(it.vector) == 128
        assert it.cached is False

    # Second execution (cache hits)
    res2 = await service.embed_chunks(chunks)
    assert res2.status == "success"
    assert res2.metrics is not None
    assert res2.metrics.cache_hits == 3
    assert res2.metrics.cache_misses == 0
    for it in res2.items:
        assert it.vector is not None
        assert it.cached is True
