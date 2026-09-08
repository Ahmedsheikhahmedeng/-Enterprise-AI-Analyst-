"""Deterministic multi-dimensional case scoring engine."""

from typing import Any

from app.evaluation.config import EvaluationConfig, get_evaluation_config
from app.evaluation.metrics.citation import compute_citation_metrics
from app.evaluation.metrics.grounding import evaluate_groundedness
from app.evaluation.metrics.hallucination import detect_hallucinations
from app.evaluation.metrics.rag import compute_rag_metrics
from app.evaluation.metrics.sql import compute_sql_metrics


class DeterministicScorer:
    """Combines deterministic metric outputs into a normalized case score and pass/fail status."""

    def __init__(self, config: EvaluationConfig | None = None) -> None:
        self.config = config or get_evaluation_config()

    def score_case(
        self,
        *,
        route_expected: str,
        actual_route: str | None,
        query: str,
        actual_answer: str,
        expected_answer: str | None,
        expected_citations: list[str],
        expected_documents: list[str],
        expected_metrics: dict[str, Any],
        actual_metrics: dict[str, Any],
        evidence_items: list[dict[str, Any]],
        actual_sql: str | None = None,
        execution_success: bool = True,
        execution_error: str | None = None,
    ) -> dict[str, Any]:
        """Compute all component metrics and produce an aggregate pass/fail verdict."""
        actual_evidence_ids = [
            str(ev.get("evidence_id") or ev.get("id") or "").upper() for ev in evidence_items
        ]

        # 1. Route accuracy
        route_match = (
            1.0 if (actual_route and actual_route.lower() == route_expected.lower()) else 0.0
        )

        # 2. SQL metrics
        sql_m = compute_sql_metrics(
            actual_sql=actual_sql or "",
            execution_success=execution_success,
            error=execution_error,
            expected_semantics=None,
            actual_metrics=actual_metrics,
            expected_metrics=expected_metrics,
            tolerance_ratio=self.config.strict_numeric_tolerance_ratio,
        )

        # 3. Citation metrics
        citation_m = compute_citation_metrics(
            answer=actual_answer,
            actual_evidence_ids=actual_evidence_ids,
            expected_citations=expected_citations,
        )

        # 4. Grounding metrics
        grounding_m = evaluate_groundedness(
            answer=actual_answer,
            evidence_items=evidence_items,
        )

        # 5. Hallucination metrics
        hallucination_m = detect_hallucinations(
            answer=actual_answer,
            evidence_items=evidence_items,
            actual_evidence_ids=actual_evidence_ids,
        )

        # 6. Retrieval / RAG metrics
        retrieved_contexts = [
            str(ev.get("content") or ev.get("text") or "") for ev in evidence_items
        ]
        retrieved_chunks = [str(ev.get("chunk_id") or ev.get("id") or "") for ev in evidence_items]
        rag_m = compute_rag_metrics(
            query=query,
            answer=actual_answer,
            retrieved_contexts=retrieved_contexts,
            retrieved_chunks=retrieved_chunks,
            relevant_chunks=expected_documents,
        )

        # Determine overall case pass/fail
        passed = True
        failure_reasons: list[str] = []

        if route_expected.lower() in ("sql", "hybrid"):
            if sql_m.sql_safety < 1.0:
                passed = False
                failure_reasons.append("Hazardous SQL detected.")
            if sql_m.sql_validity < 1.0:
                passed = False
                failure_reasons.append("SQL execution failed.")
            if expected_metrics and sql_m.result_correctness < 0.90:
                passed = False
                failure_reasons.append("Numerical SQL metric mismatch.")

        if route_expected.lower() in ("rag", "hybrid"):
            if grounding_m.groundedness_score < 0.5:
                passed = False
                failure_reasons.append("Answer is ungrounded.")
            if citation_m.phantom_citation_rate > 0.0:
                passed = False
                failure_reasons.append("Phantom citations referenced.")

        if route_match < 1.0:
            passed = False
            failure_reasons.append(
                f"Route mismatch: expected {route_expected}, got {actual_route}."
            )

        return {
            "passed": passed,
            "failure_reason": "; ".join(failure_reasons) if failure_reasons else None,
            "route_accuracy": route_match,
            "retrieval_score": rag_m.context_precision,
            "rag_score": rag_m.faithfulness,
            "sql_score": sql_m.result_correctness if expected_metrics else sql_m.sql_validity,
            "grounding_score": grounding_m.groundedness_score,
            "citation_score": citation_m.citation_precision,
            "hallucination_score": hallucination_m.hallucination_score,
            "details": {
                "sql": sql_m.to_dict(),
                "citation": citation_m.to_dict(),
                "grounding": grounding_m.to_dict(),
                "hallucination": hallucination_m.to_dict(),
                "rag": rag_m.to_dict(),
            },
        }
