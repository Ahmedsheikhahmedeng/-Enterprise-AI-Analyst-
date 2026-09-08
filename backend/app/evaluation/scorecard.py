"""Scorecard generation and weighted multidimensional benchmark aggregation."""

from uuid import UUID

from app.evaluation.config import EvaluationConfig, get_evaluation_config
from app.evaluation.metrics.latency import compute_latency_percentiles
from app.evaluation.models import Scorecard
from app.models.evaluation import EvaluationCaseResult


class ScorecardGenerator:
    """Aggregates individual evaluation case results into an executive scorecard."""

    def __init__(self, config: EvaluationConfig | None = None) -> None:
        self.config = config or get_evaluation_config()

    def generate(
        self,
        *,
        run_id: UUID,
        dataset_id: UUID,
        dataset_version: int,
        results: list[EvaluationCaseResult],
    ) -> Scorecard:
        """Compile comprehensive QA, performance, and cost scorecards from case results."""
        total = len(results)
        if total == 0:
            return Scorecard(
                run_id=run_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                pass_rate=0.0,
                route_accuracy=0.0,
                retrieval_recall_at_5=0.0,
                citation_precision=0.0,
                groundedness=0.0,
                sql_accuracy=0.0,
                hybrid_accuracy=0.0,
                hallucination_rate=0.0,
                p50_latency_ms=0.0,
                p75_latency_ms=0.0,
                p90_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                cost_per_query_usd=0.0,
                total_cost_usd=0.0,
                quality_score=0.0,
                performance_score=0.0,
                cost_score=0.0,
                overall_score=0.0,
            )

        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        pass_rate = passed / total

        # QA Metrics
        route_acc = (
            sum(
                1
                for r in results
                if (
                    r.actual_route
                    and r.expected_route
                    and r.actual_route.lower() == r.expected_route.lower()
                )
            )
            / total
        )

        retrieval_scores = [r.retrieval_score for r in results]
        avg_retrieval = sum(retrieval_scores) / total

        citation_scores = [r.citation_score for r in results]
        avg_citation = sum(citation_scores) / total

        grounding_scores = [r.grounding_score for r in results]
        avg_grounding = sum(grounding_scores) / total

        sql_cases = [r for r in results if r.expected_route == "sql"]
        avg_sql = (sum(r.sql_score for r in sql_cases) / len(sql_cases)) if sql_cases else 1.0

        hybrid_cases = [r for r in results if r.expected_route == "hybrid"]
        hybrid_acc = (
            (sum(1 for r in hybrid_cases if r.passed) / len(hybrid_cases)) if hybrid_cases else 1.0
        )

        hallucination_scores = [r.hallucination_score for r in results]
        avg_clean_score = sum(hallucination_scores) / total
        hallucination_rate = max(0.0, 1.0 - avg_clean_score)

        # Latency statistics
        latencies = [r.latency_ms for r in results]
        percentiles = compute_latency_percentiles(latencies)

        # Cost statistics
        total_cost = sum(r.estimated_cost for r in results)
        cost_per_query = total_cost / total

        # Segmented Scores
        # 1. Quality Score
        w = self.config.scorecard_weights
        quality_score = (
            w.get("retrieval", 0.20) * avg_retrieval
            + w.get("sql", 0.20) * avg_sql
            + w.get("grounding", 0.20) * avg_grounding
            + w.get("citation", 0.15) * avg_citation
            + w.get("answer", 0.15) * route_acc
            + w.get("hallucination", 0.10) * avg_clean_score
        )

        # 2. Performance Score (1.0 for <= 500ms, decreasing to 0.0 at 5000ms)
        p95 = percentiles["p95"]
        if p95 <= 500.0:
            performance_score = 1.0
        elif p95 >= 5000.0:
            performance_score = 0.1
        else:
            performance_score = max(0.1, 1.0 - ((p95 - 500.0) / 4500.0))

        # 3. Cost Score (1.0 for <= $0.005/query, decreasing at $0.05/query)
        if cost_per_query <= 0.005:
            cost_score = 1.0
        elif cost_per_query >= 0.05:
            cost_score = 0.2
        else:
            cost_score = max(0.2, 1.0 - ((cost_per_query - 0.005) / 0.045))

        # 4. Overall Score (quality 70%, performance 20%, cost 10%)
        overall_score = (0.70 * quality_score) + (0.20 * performance_score) + (0.10 * cost_score)

        return Scorecard(
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            pass_rate=pass_rate,
            route_accuracy=route_acc,
            retrieval_recall_at_5=avg_retrieval,
            citation_precision=avg_citation,
            groundedness=avg_grounding,
            sql_accuracy=avg_sql,
            hybrid_accuracy=hybrid_acc,
            hallucination_rate=hallucination_rate,
            p50_latency_ms=percentiles["p50"],
            p75_latency_ms=percentiles["p75"],
            p90_latency_ms=percentiles["p90"],
            p95_latency_ms=percentiles["p95"],
            p99_latency_ms=percentiles["p99"],
            cost_per_query_usd=cost_per_query,
            total_cost_usd=total_cost,
            quality_score=quality_score,
            performance_score=performance_score,
            cost_score=cost_score,
            overall_score=overall_score,
        )
