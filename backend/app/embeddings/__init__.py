"""Embeddings subsystem for Enterprise AI Analyst."""

from app.embeddings.batching import create_batches, process_batches_with_concurrency
from app.embeddings.cache import (
    EmbeddingCache,
    InMemoryEmbeddingCache,
    NoopEmbeddingCache,
    RedisEmbeddingCache,
    build_embedding_cache_key,
)
from app.embeddings.config import EmbeddingConfig
from app.embeddings.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingCacheError,
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingInvalidInputError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
    EmbeddingValidationError,
)
from app.embeddings.hashing import compute_embedding_input_hash
from app.embeddings.models import (
    EmbeddingBatchResult,
    EmbeddingItem,
    EmbeddingUsageMetrics,
    EmbeddingVector,
)
from app.embeddings.normalization import l2_normalize_vector, normalize_embedding_text
from app.embeddings.pricing import EmbeddingPricing
from app.embeddings.providers import (
    EmbeddingProvider,
    EmbeddingProviderFactory,
    LocalDeterministicEmbeddingProvider,
    OpenAIEmbeddingProvider,
    ProviderEmbeddingResponse,
)
from app.embeddings.service import EmbeddingService
from app.embeddings.text_builder import EmbeddingTextBuilder
from app.embeddings.tokenizer import EmbeddingTokenizer, UniversalEmbeddingTokenizer
from app.embeddings.validators import validate_embedding_vector

__all__ = [
    "EmbeddingConfig",
    "EmbeddingError",
    "EmbeddingConfigurationError",
    "EmbeddingProviderError",
    "EmbeddingAuthenticationError",
    "EmbeddingRateLimitError",
    "EmbeddingTimeoutError",
    "EmbeddingInvalidInputError",
    "EmbeddingValidationError",
    "EmbeddingDimensionError",
    "EmbeddingCacheError",
    "EmbeddingVector",
    "EmbeddingItem",
    "EmbeddingUsageMetrics",
    "EmbeddingBatchResult",
    "normalize_embedding_text",
    "l2_normalize_vector",
    "EmbeddingTokenizer",
    "UniversalEmbeddingTokenizer",
    "EmbeddingTextBuilder",
    "compute_embedding_input_hash",
    "validate_embedding_vector",
    "EmbeddingPricing",
    "EmbeddingCache",
    "NoopEmbeddingCache",
    "InMemoryEmbeddingCache",
    "RedisEmbeddingCache",
    "build_embedding_cache_key",
    "EmbeddingProvider",
    "ProviderEmbeddingResponse",
    "EmbeddingProviderFactory",
    "LocalDeterministicEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "create_batches",
    "process_batches_with_concurrency",
    "EmbeddingService",
]
