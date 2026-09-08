"""Cross-Encoder Reranking domain package."""

from app.reranking.config import RerankerConfig, get_reranker_config
from app.reranking.exceptions import (
    RerankerConfigurationError,
    RerankerInferenceError,
    RerankerInputError,
    RerankerModelLoadError,
    RerankerTenantError,
    RerankerTimeoutError,
    RerankerUnavailableError,
    RerankingError,
)
from app.reranking.models import (
    RerankedCandidate,
    RerankingDiagnostics,
    RerankingLatency,
    RerankingResult,
    RerankPair,
)
from app.reranking.providers import (
    LocalDeterministicCrossEncoderProvider,
    RerankerProvider,
    RerankerProviderFactory,
    SentenceTransformersRerankerProvider,
)
from app.reranking.service import CrossEncoderRerankingService

__all__ = [
    "CrossEncoderRerankingService",
    "LocalDeterministicCrossEncoderProvider",
    "RerankPair",
    "RerankedCandidate",
    "RerankerConfig",
    "RerankerConfigurationError",
    "RerankerInferenceError",
    "RerankerInputError",
    "RerankerModelLoadError",
    "RerankerProvider",
    "RerankerProviderFactory",
    "RerankerTenantError",
    "RerankerTimeoutError",
    "RerankerUnavailableError",
    "RerankingDiagnostics",
    "RerankingError",
    "RerankingLatency",
    "RerankingResult",
    "SentenceTransformersRerankerProvider",
    "get_reranker_config",
]
