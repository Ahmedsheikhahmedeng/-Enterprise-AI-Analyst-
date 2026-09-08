"""Reliability reporting and executive summary generators."""

from datetime import UTC, datetime
from typing import Any

from app.reliability.enums import ReadinessDecision


class ReliabilityReportGenerator:
    """Produces comprehensive executive summaries and reliability score reports."""

    @staticmethod
    def generate_report(
        *,
        scenarios_count: int,
        runs: list[dict[str, Any]],
        scorecard: dict[str, Any] | None,
        readiness: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Aggregate test execution logs into executive summary."""
        total_runs = len(runs)
        passed_runs = sum(1 for r in runs if r.get("status") == "PASSED")
        failed_runs = total_runs - passed_runs

        valid_mttds = [r["mttd_seconds"] for r in runs if r.get("mttd_seconds") is not None]
        avg_mttd = round(sum(valid_mttds) / len(valid_mttds), 3) if valid_mttds else 0.0

        valid_mttrs = [r["mttr_seconds"] for r in runs if r.get("mttr_seconds") is not None]
        avg_mttr = round(sum(valid_mttrs) / len(valid_mttrs), 3) if valid_mttrs else 0.0

        composite_score = scorecard.get("composite_score", 100.0) if scorecard else 100.0
        decision_str = (
            readiness.get("decision", ReadinessDecision.READY.value)
            if readiness
            else ReadinessDecision.READY.value
        )

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_scenarios_defined": scenarios_count,
            "total_runs_executed": total_runs,
            "passed_runs": passed_runs,
            "failed_runs": failed_runs,
            "average_mttd_seconds": avg_mttd,
            "average_mttr_seconds": avg_mttr,
            "readiness_decision": decision_str,
            "composite_reliability_score": composite_score,
            "scorecard": scorecard,
            "latest_readiness": readiness,
            "recent_runs": runs[:10],
        }
