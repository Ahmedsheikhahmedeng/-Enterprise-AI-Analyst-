"""Unit tests for Enterprise AI Evaluation & Quality Framework.

Tests all evaluation metrics, scoring algorithms, deterministic judges,
percentiles, and regression detection logic without external network dependencies.
"""

import math
import uuid

import pytest

from app.evaluation.config import EvaluationConfig
from app.evaluation.metrics.citation import compute_citation_metrics
from app.evaluation.metrics.cost import compute_cost_summary
from app.evaluation.metrics.grounding import evaluate_groundedness
from app.evaluation.metrics.hallucination import detect_hallucinations
from app.evaluation.metrics.latency import compute_latency_percentiles, compute_percentile
from app.evaluation.metrics.rag import (
    answer_relevance,
    context_precision,
    context_recall,
    extract_claims,
    faithfulness,
)
from app.evaluation.metrics.retrieval import (
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.metrics.sql import (
    evaluate_numeric_accuracy,
    evaluate_result_correctness,
    evaluate_sql_safety,
    evaluate_sql_validity,
)
from app.evaluation.models import Scorecard
from app.evaluation.regression import RegressionDetector
from app.evaluation.scorecard import ScorecardGenerator
from app.evaluation.scorers.deterministic import DeterministicScorer
from app.evaluation.scorers.llm_judge import DeterministicJudgeProvider
from app.models.evaluation import EvaluationCaseResult


class TestRetrievalMetrics:
    """Deterministic Information Retrieval (IR) evaluation metrics."""

    def test_recall_at_k(self) -> None:
        retrieved = ["doc1", "doc2", "doc3", "doc4"]
        relevant = ["doc2", "doc4", "doc5"]

        # K = 1 -> ["doc1"], matches 0 -> 0.0
        assert recall_at_k(retrieved, relevant, k=1) == 0.0
        # K = 2 -> ["doc1", "doc2"], matches 1/3
        assert recall_at_k(retrieved, relevant, k=2) == pytest.approx(1 / 3, rel=1e-3)
        # K = 4 -> ["doc1", "doc2", "doc3", "doc4"], matches 2/3
        assert recall_at_k(retrieved, relevant, k=4) == pytest.approx(2 / 3, rel=1e-3)

        # Empty retrieved -> 0.0
        assert recall_at_k([], relevant, k=5) == 0.0
        # Empty relevant is vacuously true -> 1.0
        assert recall_at_k(retrieved, [], k=5) == 1.0

    def test_precision_at_k(self) -> None:
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = ["doc1", "doc3"]

        # K = 2 -> ["doc1", "doc2"], matches 1 -> 1/2 = 0.5
        assert precision_at_k(retrieved, relevant, k=2) == 0.5
        # K = 5 -> matches 2 -> 2/5 = 0.4
        assert precision_at_k(retrieved, relevant, k=5) == 0.4
        # K = 0 edge
        assert precision_at_k(retrieved, relevant, k=0) == 0.0

    def test_hit_rate_at_k(self) -> None:
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = ["doc3", "doc9"]

        assert hit_rate_at_k(retrieved, relevant, k=1) == 0.0
        assert hit_rate_at_k(retrieved, relevant, k=2) == 0.0
        assert hit_rate_at_k(retrieved, relevant, k=3) == 1.0

    def test_reciprocal_rank(self) -> None:
        assert reciprocal_rank(["docA", "docB", "docC"], ["docB"]) == 0.5
        assert reciprocal_rank(["docA", "docB", "docC"], ["docA"]) == 1.0
        assert reciprocal_rank(["docA", "docB", "docC"], ["docZ"]) == 0.0

    def test_ndcg_at_k(self) -> None:
        retrieved = ["docA", "docB", "docC", "docD", "docE"]
        # Match at rank 1
        assert ndcg_at_k(retrieved, ["docA"], k=5) == 1.0
        # Match at rank 2
        # DCG@2 = 1 / log2(3), IDCG@2 = 1 / log2(2) = 1.0
        expected = (1.0 / math.log2(3)) / (1.0 / math.log2(2))
        assert ndcg_at_k(retrieved, ["docB"], k=5) == pytest.approx(expected, rel=1e-3)
        # No match
        assert ndcg_at_k(retrieved, ["docZ"], k=5) == 0.0


class TestRAGMetrics:
    """RAG pipeline evaluation metrics (Recall, Precision, Relevance, Faithfulness)."""

    def test_extract_claims(self) -> None:
        text = "Revenue grew by 15 percent. Profits reached ten million dollars. Operating margin was healthy."
        claims = extract_claims(text)
        assert len(claims) >= 2
        assert any("Revenue grew" in c for c in claims)

    def test_context_recall(self) -> None:
        contexts = ["Revenue was $100M in Q1 and $120M in Q2."]
        facts = ["Revenue reached $100M in Q1."]
        assert context_recall(contexts, facts) == 1.0

        irrelevant_contexts = ["Weather was sunny in San Francisco."]
        assert context_recall(irrelevant_contexts, facts) == 0.0

    def test_context_precision(self) -> None:
        retrieved_chunks = ["chunk1", "chunk2", "chunk3"]
        relevant_chunks = ["chunk1", "chunk9"]
        score = context_precision(retrieved_chunks, relevant_chunks)
        assert score == pytest.approx(1 / 3, rel=1e-3)

    def test_answer_relevance(self) -> None:
        query = "What was Q4 revenue for the company?"
        good_answer = "Q4 revenue was $120M according to company filings."
        bad_answer = "Apples and oranges grow in Mediterranean regions."
        assert answer_relevance(query, good_answer) >= 0.4
        assert answer_relevance(query, bad_answer) < 0.2

    def test_faithfulness(self) -> None:
        contexts = ["Acme Corp reported $50M profit in 2024."]
        faithful_claims = ["Acme Corp reported $50M profit in 2024."]
        unfaithful_claims = ["Acme Corp filed for bankruptcy with massive debts."]
        assert faithfulness(faithful_claims, contexts) == 1.0
        assert faithfulness(unfaithful_claims, contexts) == 0.0


class TestSQLMetrics:
    """SQL safety, validity, and semantic numeric correctness."""

    def test_sql_safety(self) -> None:
        assert evaluate_sql_safety("SELECT * FROM sales;") == 1.0
        assert (
            evaluate_sql_safety("SELECT quarter, SUM(revenue) FROM sales GROUP BY quarter;") == 1.0
        )

        unsafe_queries = [
            "DROP TABLE sales;",
            "DELETE FROM sales WHERE id = 1;",
            "INSERT INTO sales VALUES (1, 'Q1', 100);",
            "UPDATE sales SET revenue = 0;",
            "TRUNCATE sales;",
            "ALTER TABLE sales ADD COLUMN test INT;",
        ]
        for query in unsafe_queries:
            assert evaluate_sql_safety(query) == 0.0

    def test_sql_validity(self) -> None:
        assert evaluate_sql_validity(execution_success=True, error=None) == 1.0
        assert evaluate_sql_validity(execution_success=False, error="Syntax error") == 0.0

    def test_numeric_accuracy_with_tolerances(self) -> None:
        # Exact match
        score = evaluate_numeric_accuracy(120000000, 120000000, tolerance_ratio=0.0)
        assert score == 1.0

        # Tolerance 0.1% (0.001) -> expected 1000, actual 1000.5 -> 0.05% diff -> within 0.1%
        score = evaluate_numeric_accuracy(1000.5, 1000.0, tolerance_ratio=0.001)
        assert score == 1.0

        # Tolerance 1% (0.01) -> expected 100, actual 100.8 -> 0.8% diff -> within 1%
        score = evaluate_numeric_accuracy(100.8, 100.0, tolerance_ratio=0.01)
        assert score == 1.0

        # Outside 1% (0.01) but inside 5% (0.05)
        score_1 = evaluate_numeric_accuracy(103.0, 100.0, tolerance_ratio=0.01)
        assert score_1 == 0.0
        score_5 = evaluate_numeric_accuracy(103.0, 100.0, tolerance_ratio=0.05)
        assert score_5 == 1.0

    def test_result_correctness(self) -> None:
        actual_metrics = {"revenue": 100.0}
        expected_metrics = {"revenue": 100.0}
        assert evaluate_result_correctness(actual_metrics, expected_metrics) == 1.0

        mismatched_metrics = {"revenue": 999.0}
        assert evaluate_result_correctness(mismatched_metrics, expected_metrics) == 0.0


class TestCitationAndGroundingMetrics:
    """Citation extraction, precision/recall, and groundedness evaluation."""

    def test_citation_metrics(self) -> None:
        answer = "Revenue was $120M [S1] and expenses were $80M [R1]."
        available_evidence = ["S1", "R1", "R2"]
        expected_citations = ["S1", "R1"]

        metrics = compute_citation_metrics(answer, available_evidence, expected_citations)
        assert metrics.citation_precision == 1.0
        assert metrics.citation_recall == 1.0
        assert metrics.phantom_citation_rate == 0.0

        # Phantom citation test
        bad_answer = "Revenue was $120M [X99]."
        metrics_bad = compute_citation_metrics(bad_answer, available_evidence, expected_citations)
        assert metrics_bad.phantom_citation_rate == 1.0

    def test_groundedness_evaluation(self) -> None:
        # Fully grounded
        evidence = [
            {
                "evidence_id": "S1",
                "content": "Revenue declined by 12% in Q4 2025 due to supply constraints.",
            }
        ]
        claim_grounded = "Revenue declined by 12% in Q4 2025 [S1]."
        result = evaluate_groundedness(claim_grounded, evidence)
        assert result.groundedness_label == "fully_grounded"
        assert result.groundedness_score >= 0.8

        # Ungrounded
        claim_ungrounded = "The company purchased 500 commercial passenger airplanes."
        result_un = evaluate_groundedness(claim_ungrounded, evidence)
        assert result_un.groundedness_label == "ungrounded"
        assert result_un.groundedness_score == 0.0


class TestHallucinationDetection:
    """Deterministic identification of hallucinations and unsupported claims."""

    def test_detect_numeric_hallucinations(self) -> None:
        answer = "We made $450M in profits and grew by 75% [S1]."
        evidence_items = [{"content": "We made $100M in profits and grew by 10%."}]
        available_citations = ["S1"]

        metrics = detect_hallucinations(answer, evidence_items, available_citations)
        assert metrics.unsupported_numeric_count > 0 or metrics.unsupported_percentage_count > 0

    def test_detect_phantom_citation(self) -> None:
        answer = "Operations ceased in March [Ghost1]."
        evidence_items = [{"content": "Operations ceased in March."}]
        available_citations = ["ValidDoc1"]

        metrics = detect_hallucinations(answer, evidence_items, available_citations)
        assert metrics.phantom_citation_count == 1


class TestLatencyAndCostMetrics:
    """Latency percentile calculations and token cost tracking."""

    def test_percentiles(self) -> None:
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        p50 = compute_percentile(values, 50)
        p90 = compute_percentile(values, 90)
        p95 = compute_percentile(values, 95)

        assert 45.0 <= p50 <= 55.0
        assert 85.0 <= p90 <= 95.0
        assert 90.0 <= p95 <= 100.0

        percentiles = compute_latency_percentiles(values)
        assert percentiles["p50"] == pytest.approx(p50, rel=1e-2)
        assert percentiles["p95"] == pytest.approx(p95, rel=1e-2)

    def test_cost_calculation(self) -> None:
        cost = compute_cost_summary(total_cost_usd=0.025, total_cases=10, passed_cases=10)
        assert cost["total_cost_usd"] == 0.025
        assert cost["cost_per_case_usd"] == 0.0025
        assert cost["cost_per_1k_cases_usd"] == 2.5


class TestScorecardAndScorers:
    """Aggregated Scorecard generation, weighted multi-metric scores, and LLM judge."""

    def test_deterministic_scorer(self) -> None:
        scorer = DeterministicScorer()
        score = scorer.score_case(
            route_expected="rag",
            actual_route="rag",
            query="What were total sales in Q1?",
            actual_answer="Total sales were 100 units in Q1 [S1].",
            expected_answer="Total sales were 100 units.",
            expected_citations=["S1"],
            expected_documents=["doc1"],
            expected_metrics={},
            actual_metrics={},
            evidence_items=[{"evidence_id": "S1", "content": "Total sales were 100 units in Q1."}],
        )
        assert score["passed"] is True
        assert score["citation_score"] == 1.0
        assert score["grounding_score"] >= 0.8

    def test_scorecard_generator_weighted_scores(self) -> None:
        config = EvaluationConfig()
        generator = ScorecardGenerator(config)

        case_res = EvaluationCaseResult(
            run_id=uuid.uuid4(),
            case_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            actual_route="sql",
            expected_route="sql",
            actual_answer="Revenue is $120M",
            passed=True,
            retrieval_score=1.0,
            rag_score=1.0,
            sql_score=1.0,
            grounding_score=1.0,
            citation_score=1.0,
            hallucination_score=0.0,
            latency_ms=250.0,
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.001,
            metrics_detail={"route_accuracy": 1.0},
        )

        scorecard = generator.generate(
            run_id=uuid.uuid4(),
            dataset_id=uuid.uuid4(),
            dataset_version=1,
            results=[case_res],
        )

        assert scorecard.total_cases == 1
        assert scorecard.passed_cases == 1
        assert scorecard.pass_rate == 1.0
        assert scorecard.route_accuracy == 1.0
        assert scorecard.quality_score > 0.8
        assert scorecard.performance_score > 0.7
        assert scorecard.overall_score > 0.8

    @pytest.mark.asyncio
    async def test_llm_judge_provider(self) -> None:
        judge = DeterministicJudgeProvider()
        result = await judge.evaluate(
            query="What is the revenue?",
            answer="The revenue is $120M according to audited financials.",
            evidence_texts=["The revenue is $120M."],
        )
        assert result.score >= 0.8
        assert result.label in {"good", "excellent"}
        assert len(result.reason) > 0


class TestRegressionDetection:
    """Baseline vs Candidate regression detection and threshold alerts."""

    def test_regression_detection_pass(self) -> None:
        config = EvaluationConfig()
        detector = RegressionDetector(config)

        run_id_base = uuid.uuid4()
        run_id_cand = uuid.uuid4()
        dataset_id = uuid.uuid4()

        base_sc = Scorecard(
            run_id=run_id_base,
            dataset_id=dataset_id,
            dataset_version=1,
            total_cases=10,
            passed_cases=10,
            failed_cases=0,
            pass_rate=1.0,
            route_accuracy=1.0,
            retrieval_recall_at_5=0.95,
            citation_precision=0.95,
            groundedness=0.95,
            sql_accuracy=1.0,
            hybrid_accuracy=0.95,
            hallucination_rate=0.0,
            p50_latency_ms=200.0,
            p75_latency_ms=250.0,
            p90_latency_ms=300.0,
            p95_latency_ms=350.0,
            p99_latency_ms=400.0,
            cost_per_query_usd=0.002,
            total_cost_usd=0.02,
            quality_score=0.95,
            performance_score=0.9,
            cost_score=0.9,
            overall_score=0.93,
        )

        cand_sc = Scorecard(
            run_id=run_id_cand,
            dataset_id=dataset_id,
            dataset_version=1,
            total_cases=10,
            passed_cases=10,
            failed_cases=0,
            pass_rate=1.0,
            route_accuracy=1.0,
            retrieval_recall_at_5=0.96,  # improved
            citation_precision=0.95,
            groundedness=0.95,
            sql_accuracy=1.0,
            hybrid_accuracy=0.95,
            hallucination_rate=0.0,
            p50_latency_ms=200.0,
            p75_latency_ms=250.0,
            p90_latency_ms=300.0,
            p95_latency_ms=350.0,
            p99_latency_ms=400.0,
            cost_per_query_usd=0.002,
            total_cost_usd=0.02,
            quality_score=0.96,
            performance_score=0.9,
            cost_score=0.9,
            overall_score=0.94,
        )

        report = detector.compare_runs(
            baseline_scorecard=base_sc,
            candidate_scorecard=cand_sc,
            baseline_results=[],
            candidate_results=[],
        )
        assert report.status == "PASS"
        assert len(report.new_failures) == 0

    def test_regression_detection_fail(self) -> None:
        config = EvaluationConfig(max_allowed_quality_regression=0.05)
        detector = RegressionDetector(config)

        run_id_base = uuid.uuid4()
        run_id_cand = uuid.uuid4()
        dataset_id = uuid.uuid4()

        base_sc = Scorecard(
            run_id=run_id_base,
            dataset_id=dataset_id,
            dataset_version=1,
            total_cases=10,
            passed_cases=10,
            failed_cases=0,
            pass_rate=1.0,
            route_accuracy=1.0,
            retrieval_recall_at_5=0.95,
            citation_precision=0.95,
            groundedness=0.95,
            sql_accuracy=1.0,
            hybrid_accuracy=0.95,
            hallucination_rate=0.0,
            p50_latency_ms=200.0,
            p75_latency_ms=250.0,
            p90_latency_ms=300.0,
            p95_latency_ms=350.0,
            p99_latency_ms=400.0,
            cost_per_query_usd=0.002,
            total_cost_usd=0.02,
            quality_score=0.95,
            performance_score=0.9,
            cost_score=0.9,
            overall_score=0.93,
        )

        # Degrade quality from 0.95 to 0.80 (drop of 0.15 > max 0.05)
        cand_sc = Scorecard(
            run_id=run_id_cand,
            dataset_id=dataset_id,
            dataset_version=1,
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            pass_rate=0.8,
            route_accuracy=0.8,
            retrieval_recall_at_5=0.80,
            citation_precision=0.80,
            groundedness=0.80,
            sql_accuracy=0.80,
            hybrid_accuracy=0.80,
            hallucination_rate=0.1,
            p50_latency_ms=500.0,
            p75_latency_ms=600.0,
            p90_latency_ms=700.0,
            p95_latency_ms=800.0,
            p99_latency_ms=900.0,
            cost_per_query_usd=0.005,
            total_cost_usd=0.05,
            quality_score=0.80,
            performance_score=0.6,
            cost_score=0.6,
            overall_score=0.72,
        )

        report = detector.compare_runs(
            baseline_scorecard=base_sc,
            candidate_scorecard=cand_sc,
            baseline_results=[],
            candidate_results=[],
        )
        assert report.status == "FAIL"
        assert len(report.regressions) > 0
