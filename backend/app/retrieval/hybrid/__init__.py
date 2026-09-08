"""Hybrid retrieval subsystem combining Dense Retrieval, BM25, and Reciprocal Rank Fusion."""

from app.retrieval.hybrid.models import (
    FusedCandidate,
    HybridRetrievalDiagnostics,
    HybridRetrievalLatency,
    HybridRetrievalResult,
    HybridRetrievedChunk,
)
from app.retrieval.hybrid.rrf import ReciprocalRankFusion
from app.retrieval.hybrid.service import HybridRetrievalService

__all__ = [
    "FusedCandidate",
    "HybridRetrievalDiagnostics",
    "HybridRetrievalLatency",
    "HybridRetrievalResult",
    "HybridRetrievalService",
    "HybridRetrievedChunk",
    "ReciprocalRankFusion",
]
