"""Deterministic Reliability Scorecard calculation engine based on empirical runs."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ScorecardResult:
    """Calculated reliability scores across all primary reliability categories."""

    detection_score: float
    recovery_score: float
    integrity_score: float
    degradation_score: float
    isolation_score: float
    slo_score: float
    composite_score: float
    total_scenarios_run: int
    passed_count: int
    failed_count: int
    metrics_payload: dict[str, Any]


class ReliabilityScoringEngine:
    """Calculates non-speculative, deterministic reliability scorecards."""

    # Explicit category weights summing to 1.0 (100%)
    WEIGHT_DETECTION = 0.20
    WEIGHT_RECOVERY = 0.20
    WEIGHT_INTEGRITY = 0.20
    WEIGHT_DEGRADATION = 0.15
    WEIGHT_ISOLATION = 0.15
    WEIGHT_SLO = 0.10

    @classmethod
    def calculate_scorecard(
        cls,
        runs_summary: list[dict[str, Any]],
    ) -> ScorecardResult:
        """Derive deterministic reliability scores from scenario run histories."""
        if not runs_summary:
            # Baseline when no runs executed yet
            return ScorecardResult(
                detection_score=100.0,
                recovery_score=100.0,
                integrity_score=100.0,
                degradation_score=100.0,
                isolation_score=100.0,
                slo_score=100.0,
                composite_score=100.0,
                total_scenarios_run=0,
                passed_count=0,
                failed_count=0,
                metrics_payload={"notice": "No runs executed; baseline pristine state."},
            )

        total_runs = len(runs_summary)
        passed_runs = sum(1 for r in runs_summary if r.get("status") == "PASSED")
        failed_runs = total_runs - passed_runs

        # Calculate category scores
        detection_hits = sum(1 for r in runs_summary if r.get("mttd_seconds") is not None)
        detection_score = round((detection_hits / total_runs) * 100.0, 2)

        recovery_hits = sum(
            1 for r in runs_summary if r.get("time_to_recovery_seconds") is not None
        )
        recovery_score = round((recovery_hits / total_runs) * 100.0, 2)

        integrity_fails = sum(
            1 for r in runs_summary if r.get("failure_classification") == "DATA_INTEGRITY_FAILURE"
        )
        integrity_score = round(max(0.0, 100.0 - (integrity_fails * 35.0)), 2)

        isolation_fails = sum(
            1 for r in runs_summary if r.get("failure_classification") == "ISOLATION_FAILURE"
        )
        isolation_score = round(max(0.0, 100.0 - (isolation_fails * 50.0)), 2)

        degradation_passes = sum(
            1 for r in runs_summary if r.get("status") in ("PASSED", "WARNING")
        )
        degradation_score = round((degradation_passes / total_runs) * 100.0, 2)

        slo_breaches = sum(
            1 for r in runs_summary if r.get("error_budget_consumed_pct", 0.0) >= 100.0
        )
        slo_score = round(max(0.0, 100.0 - (slo_breaches * 25.0)), 2)

        # Calculate weighted composite score
        composite = (
            (detection_score * cls.WEIGHT_DETECTION)
            + (recovery_score * cls.WEIGHT_RECOVERY)
            + (integrity_score * cls.WEIGHT_INTEGRITY)
            + (degradation_score * cls.WEIGHT_DEGRADATION)
            + (isolation_score * cls.WEIGHT_ISOLATION)
            + (slo_score * cls.WEIGHT_SLO)
        )
        composite_score = round(min(100.0, max(0.0, composite)), 2)

        return ScorecardResult(
            detection_score=detection_score,
            recovery_score=recovery_score,
            integrity_score=integrity_score,
            degradation_score=degradation_score,
            isolation_score=isolation_score,
            slo_score=slo_score,
            composite_score=composite_score,
            total_scenarios_run=total_runs,
            passed_count=passed_runs,
            failed_count=failed_runs,
            metrics_payload={
                "detection_hits": detection_hits,
                "recovery_hits": recovery_hits,
                "integrity_fails": integrity_fails,
                "isolation_fails": isolation_fails,
                "slo_breaches": slo_breaches,
            },
        )
