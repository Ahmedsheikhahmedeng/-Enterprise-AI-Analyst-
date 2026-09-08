"""Differential comparison service for models, prompts, and semantic/graph versions."""

from typing import Any

from app.continuous_evaluation.domain.models import ComparisonReport
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol


class ComparisonService:
    """Provides differential comparative evaluation across model, prompt, and schema versions."""

    def __init__(self, repository: ContinuousEvaluationRepositoryProtocol | None = None) -> None:
        self.repository = repository

    def compare_scorecards(
        self,
        comparison_type: str,  # MODEL, PROMPT, SEMANTIC, GRAPH
        baseline_id: str,
        candidate_id: str,
        baseline_scorecard: dict[str, Any],
        candidate_scorecard: dict[str, Any],
    ) -> ComparisonReport:
        """Computes metric differences and determines a winner based on composite quality and key criteria."""
        b_metrics = baseline_scorecard.get("metrics", {})
        c_metrics = candidate_scorecard.get("metrics", {})

        b_quality = baseline_scorecard.get("segmented_scores", {}).get(
            "quality_score", baseline_scorecard.get("overall_score", 0.0)
        )
        c_quality = candidate_scorecard.get("segmented_scores", {}).get(
            "quality_score", candidate_scorecard.get("overall_score", 0.0)
        )

        b_latency = baseline_scorecard.get("latency", {}).get("p95_ms", 1000.0)
        c_latency = candidate_scorecard.get("latency", {}).get("p95_ms", 1000.0)

        b_cost = baseline_scorecard.get("cost", {}).get("cost_per_query_usd", 0.01)
        c_cost = candidate_scorecard.get("cost", {}).get("cost_per_query_usd", 0.01)

        diffs: dict[str, dict[str, float]] = {
            "quality_score": {
                "baseline": round(float(b_quality), 4),
                "candidate": round(float(c_quality), 4),
                "delta": round(float(c_quality) - float(b_quality), 4),
            },
            "p95_latency_ms": {
                "baseline": round(float(b_latency), 2),
                "candidate": round(float(c_latency), 2),
                "delta": round(float(c_latency) - float(b_latency), 2),
            },
            "cost_per_query_usd": {
                "baseline": round(float(b_cost), 6),
                "candidate": round(float(c_cost), 6),
                "delta": round(float(c_cost) - float(b_cost), 6),
            },
        }

        # Add shared specific metrics (grounding, citation, sql, etc.)
        all_metric_keys = set(b_metrics.keys()).union(set(c_metrics.keys()))
        for key in all_metric_keys:
            b_v = float(b_metrics.get(key, 0.0))
            c_v = float(c_metrics.get(key, 0.0))
            diffs[key] = {
                "baseline": round(b_v, 4),
                "candidate": round(c_v, 4),
                "delta": round(c_v - b_v, 4),
            }

        # Determine winner
        # Higher quality is primary; if quality is roughly equal (within 0.01), lowest cost/latency wins
        quality_delta = float(c_quality) - float(b_quality)
        if quality_delta > 0.01:
            winner = candidate_id
            summary = f"Candidate ({candidate_id}) outperformed baseline on quality by {quality_delta * 100:.1f}%."
        elif quality_delta < -0.01:
            winner = baseline_id
            summary = f"Baseline ({baseline_id}) outperformed candidate on quality by {abs(quality_delta) * 100:.1f}%."
        else:
            # Quality equivalent, check latency & cost
            if c_cost < b_cost and c_latency <= b_latency:
                winner = candidate_id
                summary = f"Candidate ({candidate_id}) achieved comparable quality with lower cost/latency."
            elif b_cost < c_cost:
                winner = baseline_id
                summary = f"Baseline ({baseline_id}) achieved comparable quality with lower cost."
            else:
                winner = None
                summary = "Candidate and baseline exhibit comparable performance across dimensions."

        return ComparisonReport(
            comparison_type=comparison_type.upper(),
            baseline_id=baseline_id,
            candidate_id=candidate_id,
            metrics_diff=diffs,
            winner=winner,
            summary=summary,
        )
