"""Deterministic Information Retrieval (IR) evaluation metrics."""

import math
from collections.abc import Sequence

from app.evaluation.models import RetrievalMetrics


def recall_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """Calculate Recall@K: proportion of relevant items found in top-K retrieved."""
    if not relevant:
        return 1.0
    top_k = set(retrieved[:k])
    rel_set = set(relevant)
    return len(top_k & rel_set) / len(rel_set)


def precision_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """Calculate Precision@K: proportion of top-K retrieved items that are relevant."""
    if k <= 0:
        return 0.0
    top_k = set(retrieved[:k])
    rel_set = set(relevant)
    return len(top_k & rel_set) / k


def hit_rate_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """Calculate HitRate@K: binary indicator (1.0 or 0.0) if any relevant item is in top-K."""
    if not relevant:
        return 1.0
    rel_set = set(relevant)
    return 1.0 if any(item in rel_set for item in retrieved[:k]) else 0.0


def reciprocal_rank(retrieved: Sequence[str], relevant: Sequence[str]) -> float:
    """Calculate Reciprocal Rank (1/rank of first relevant item)."""
    if not relevant:
        return 1.0
    rel_set = set(relevant)
    for rank, item in enumerate(retrieved, start=1):
        if item in rel_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """Calculate Normalized Discounted Cumulative Gain (nDCG@K) under binary relevance."""
    if not relevant:
        return 1.0
    rel_set = set(relevant)
    top_k = retrieved[:k]

    dcg = sum(
        1.0 / math.log2(rank + 1) for rank, item in enumerate(top_k, start=1) if item in rel_set
    )

    ideal_k = min(len(rel_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_k + 1))

    if idcg <= 0.0:
        return 1.0 if dcg == 0.0 else 0.0
    return dcg / idcg


def compute_retrieval_metrics(
    retrieved: Sequence[str], relevant: Sequence[str]
) -> RetrievalMetrics:
    """Compute comprehensive RetrievalMetrics suite for a given retrieved rank list."""
    return RetrievalMetrics(
        recall_at_1=recall_at_k(retrieved, relevant, 1),
        recall_at_3=recall_at_k(retrieved, relevant, 3),
        recall_at_5=recall_at_k(retrieved, relevant, 5),
        recall_at_10=recall_at_k(retrieved, relevant, 10),
        precision_at_5=precision_at_k(retrieved, relevant, 5),
        hit_rate_at_1=hit_rate_at_k(retrieved, relevant, 1),
        hit_rate_at_3=hit_rate_at_k(retrieved, relevant, 3),
        hit_rate_at_5=hit_rate_at_k(retrieved, relevant, 5),
        hit_rate_at_10=hit_rate_at_k(retrieved, relevant, 10),
        mrr=reciprocal_rank(retrieved, relevant),
        ndcg_at_5=ndcg_at_k(retrieved, relevant, 5),
    )
