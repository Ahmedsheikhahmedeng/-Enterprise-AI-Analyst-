"""Sparse retrieval subsystem implementing multilingual lexical analysis and BM25."""

from app.retrieval.sparse.analyzer import MultilingualSparseAnalyzer, turkish_lower
from app.retrieval.sparse.bm25 import BM25Encoder
from app.retrieval.sparse.models import (
    AnalyzedText,
    SparseRetrievalCandidate,
    SparseRetrievalResult,
    TenantCorpusStats,
    TokenTerm,
)
from app.retrieval.sparse.service import SparseRetrievalService
from app.retrieval.sparse.stats import (
    TenantCorpusStatsManager,
    get_tenant_corpus_stats_manager,
)

__all__ = [
    "AnalyzedText",
    "BM25Encoder",
    "MultilingualSparseAnalyzer",
    "SparseRetrievalCandidate",
    "SparseRetrievalResult",
    "SparseRetrievalService",
    "TenantCorpusStats",
    "TenantCorpusStatsManager",
    "get_tenant_corpus_stats_manager",
    "TokenTerm",
    "turkish_lower",
]
