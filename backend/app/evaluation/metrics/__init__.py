"""Exported metrics functions for Information Retrieval, RAG, SQL, Grounding, and Citations."""

from app.evaluation.metrics.citation import (
    compute_citation_metrics,
    extract_citations_from_text,
)
from app.evaluation.metrics.cost import compute_cost_summary
from app.evaluation.metrics.grounding import evaluate_groundedness
from app.evaluation.metrics.hallucination import detect_hallucinations
from app.evaluation.metrics.latency import (
    compute_latency_percentiles,
    compute_percentile,
)
from app.evaluation.metrics.rag import (
    answer_relevance,
    compute_rag_metrics,
    context_precision,
    context_recall,
    faithfulness,
)
from app.evaluation.metrics.retrieval import (
    compute_retrieval_metrics,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.metrics.sql import (
    compute_sql_metrics,
    evaluate_numeric_accuracy,
    evaluate_result_correctness,
    evaluate_sql_safety,
    evaluate_sql_semantic_correctness,
    evaluate_sql_validity,
)

__all__ = [
    "recall_at_k",
    "precision_at_k",
    "hit_rate_at_k",
    "reciprocal_rank",
    "ndcg_at_k",
    "compute_retrieval_metrics",
    "context_recall",
    "context_precision",
    "answer_relevance",
    "faithfulness",
    "compute_rag_metrics",
    "evaluate_sql_safety",
    "evaluate_sql_validity",
    "evaluate_sql_semantic_correctness",
    "evaluate_numeric_accuracy",
    "evaluate_result_correctness",
    "compute_sql_metrics",
    "extract_citations_from_text",
    "compute_citation_metrics",
    "evaluate_groundedness",
    "detect_hallucinations",
    "compute_percentile",
    "compute_latency_percentiles",
    "compute_cost_summary",
]
