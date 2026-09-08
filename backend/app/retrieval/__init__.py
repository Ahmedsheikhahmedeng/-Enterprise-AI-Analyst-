"""Retrieval package for Enterprise AI Analyst (Dense, Sparse BM25, and Hybrid RRF)."""

from app.retrieval.config import (
    BM25Config,
    HybridRetrievalConfig,
    RetrievalConfig,
    get_hybrid_retrieval_config,
    get_retrieval_config,
)
from app.retrieval.exceptions import (
    InvalidQueryError,
    RetrievalError,
    RetrievalTenantError,
    RetrievalTimeoutError,
    RetrievalValidationError,
    VectorSearchError,
)
from app.retrieval.hybrid.models import (
    FusedCandidate,
    HybridRetrievalDiagnostics,
    HybridRetrievalLatency,
    HybridRetrievalResult,
    HybridRetrievedChunk,
)
from app.retrieval.hybrid.rrf import ReciprocalRankFusion
from app.retrieval.hybrid.service import HybridRetrievalService
from app.retrieval.models import (
    DenseRetrievalResult,
    RetrievalDiagnostics,
    RetrievedChunk,
)
from app.retrieval.schemas import (
    DenseRetrievalRequest,
    DenseRetrievalResponse,
    HybridDiagnosticsResponse,
    HybridLatencyBreakdown,
    HybridRetrievalRequest,
    HybridRetrievalResponse,
    HybridRetrievedChunkResponse,
    RetrievalDiagnosticsResponse,
    RetrievalLatencyBreakdown,
    RetrievedChunkResponse,
)
from app.retrieval.service import DenseRetrievalService
from app.retrieval.sparse.analyzer import MultilingualSparseAnalyzer
from app.retrieval.sparse.bm25 import BM25Encoder
from app.retrieval.sparse.service import SparseRetrievalService

__all__ = [
    "BM25Config",
    "BM25Encoder",
    "DenseRetrievalRequest",
    "DenseRetrievalResponse",
    "DenseRetrievalResult",
    "DenseRetrievalService",
    "FusedCandidate",
    "HybridDiagnosticsResponse",
    "HybridLatencyBreakdown",
    "HybridRetrievalConfig",
    "HybridRetrievalDiagnostics",
    "HybridRetrievalLatency",
    "HybridRetrievalRequest",
    "HybridRetrievalResponse",
    "HybridRetrievalResult",
    "HybridRetrievalService",
    "HybridRetrievedChunk",
    "HybridRetrievedChunkResponse",
    "InvalidQueryError",
    "MultilingualSparseAnalyzer",
    "ReciprocalRankFusion",
    "RetrievalConfig",
    "RetrievalDiagnostics",
    "RetrievalDiagnosticsResponse",
    "RetrievalError",
    "RetrievalLatencyBreakdown",
    "RetrievalTenantError",
    "RetrievalTimeoutError",
    "RetrievalValidationError",
    "RetrievedChunk",
    "RetrievedChunkResponse",
    "SparseRetrievalService",
    "VectorSearchError",
    "get_hybrid_retrieval_config",
    "get_retrieval_config",
]
