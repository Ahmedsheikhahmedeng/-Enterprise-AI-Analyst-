"""Regression detection and comparative analysis against baseline benchmark runs."""

from typing import Any

from app.evaluation.config import EvaluationConfig, get_evaluation_config
from app.evaluation.models import RegressionReport, Scorecard
from app.models.evaluation import EvaluationCaseResult


class RegressionDetector:
    """Detects quality degradation, latency regressions, and new failure modes."""

    def __init__(self, config: EvaluationConfig | None = None) -> None:
        self.config = config or get_evaluation_config()

    def compare_runs(
        self,
        *,
        baseline_scorecard: Scorecard,
        candidate_scorecard: Scorecard,
        baseline_results: list[EvaluationCaseResult] | None = None,
        candidate_results: list[EvaluationCaseResult] | None = None,
    ) -> RegressionReport:
        """Compare candidate benchmark run against baseline and generate regression verdict."""
        # Calculate deltas
        quality_delta = candidate_scorecard.quality_score - baseline_scorecard.quality_score
        retrieval_delta = (
            candidate_scorecard.retrieval_recall_at_5 - baseline_scorecard.retrieval_recall_at_5
        )
        grounding_delta = candidate_scorecard.groundedness - baseline_scorecard.groundedness
        sql_delta = candidate_scorecard.sql_accuracy - baseline_scorecard.sql_accuracy

        b_p95 = baseline_scorecard.p95_latency_ms
        c_p95 = candidate_scorecard.p95_latency_ms
        latency_p95_delta_pct = ((c_p95 - b_p95) / b_p95) if b_p95 > 0 else 0.0

        b_cost = baseline_scorecard.cost_per_query_usd
        c_cost = candidate_scorecard.cost_per_query_usd
        cost_delta_pct = ((c_cost - b_cost) / b_cost) if b_cost > 0 else 0.0

        regressions: list[dict[str, Any]] = []
        status = "PASS"

        # Check Quality Regression
        if quality_delta < -self.config.max_allowed_quality_regression:
            status = "FAIL"
            regressions.append(
                {
                    "metric": "quality_score",
                    "severity": "high",
                    "baseline": baseline_scorecard.quality_score,
                    "candidate": candidate_scorecard.quality_score,
                    "delta": round(quality_delta, 4),
                    "threshold": -self.config.max_allowed_quality_regression,
                    "message": f"Quality score dropped by {abs(quality_delta) * 100:.1f}%, exceeding {self.config.max_allowed_quality_regression * 100:.1f}% threshold.",
                }
            )

        # Check Retrieval Regression
        if retrieval_delta < -self.config.max_allowed_retrieval_regression:
            status = "FAIL"
            regressions.append(
                {
                    "metric": "retrieval_recall@5",
                    "severity": "high",
                    "baseline": baseline_scorecard.retrieval_recall_at_5,
                    "candidate": candidate_scorecard.retrieval_recall_at_5,
                    "delta": round(retrieval_delta, 4),
                    "threshold": -self.config.max_allowed_retrieval_regression,
                    "message": f"Retrieval recall@5 dropped by {abs(retrieval_delta) * 100:.1f}%.",
                }
            )

        # Check Grounding Regression
        if grounding_delta < -self.config.max_allowed_grounding_regression:
            status = "FAIL"
            regressions.append(
                {
                    "metric": "groundedness",
                    "severity": "high",
                    "baseline": baseline_scorecard.groundedness,
                    "candidate": candidate_scorecard.groundedness,
                    "delta": round(grounding_delta, 4),
                    "threshold": -self.config.max_allowed_grounding_regression,
                    "message": f"Groundedness dropped by {abs(grounding_delta) * 100:.1f}%.",
                }
            )

        # Check Minimum Quality Threshold
        if candidate_scorecard.quality_score < self.config.min_quality_score:
            status = "FAIL"
            regressions.append(
                {
                    "metric": "min_quality_score",
                    "severity": "critical",
                    "baseline": baseline_scorecard.quality_score,
                    "candidate": candidate_scorecard.quality_score,
                    "delta": round(quality_delta, 4),
                    "threshold": self.config.min_quality_score,
                    "message": f"Candidate quality score {candidate_scorecard.quality_score:.2f} is below minimum requirement {self.config.min_quality_score:.2f}.",
                }
            )

        # Check Latency Increase
        if latency_p95_delta_pct > self.config.max_allowed_latency_increase_ratio:
            if status != "FAIL":
                status = "WARNING"
            regressions.append(
                {
                    "metric": "p95_latency",
                    "severity": "medium",
                    "baseline": b_p95,
                    "candidate": c_p95,
                    "delta": round(latency_p95_delta_pct, 4),
                    "threshold": self.config.max_allowed_latency_increase_ratio,
                    "message": f"P95 latency increased by {latency_p95_delta_pct * 100:.1f}%.",
                }
            )

        # Check New Failures
        new_failures: list[str] = []
        if baseline_results and candidate_results:
            baseline_passed_cases = {str(r.case_id) for r in baseline_results if r.passed}
            for cand_r in candidate_results:
                cid = str(cand_r.case_id)
                if not cand_r.passed and cid in baseline_passed_cases:
                    new_failures.append(cid)

            if new_failures:
                regressions.append(
                    {
                        "metric": "new_failures",
                        "severity": "high",
                        "count": len(new_failures),
                        "cases": new_failures,
                        "message": f"{len(new_failures)} case(s) that previously passed are now failing.",
                    }
                )
                if status != "FAIL":
                    status = "WARNING"

        return RegressionReport(
            baseline_run_id=baseline_scorecard.run_id,
            candidate_run_id=candidate_scorecard.run_id,
            status=status,
            quality_delta=quality_delta,
            retrieval_delta=retrieval_delta,
            grounding_delta=grounding_delta,
            sql_delta=sql_delta,
            latency_p95_delta_pct=latency_p95_delta_pct,
            cost_delta_pct=cost_delta_pct,
            new_failures=new_failures,
            regressions=regressions,
        )
