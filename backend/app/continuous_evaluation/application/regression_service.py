"""Regression detection service with multi-tier severity and statistical significance."""

import math
import uuid

from app.continuous_evaluation.domain.enums import (
    DifficultyLevel,
    RegressionSeverity,
)
from app.continuous_evaluation.domain.models import CaseLevelDiff, RegressionFinding
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol
from app.models.evaluation import EvaluationCaseResult
from app.observability.instrumentation.continuous_evaluation import (
    ContinuousEvaluationInstrumentation,
)


class SignificanceAnalyzer:
    """Analyzes statistical significance of metric shifts between evaluation runs."""

    def __init__(self, min_samples: int = 10, significance_alpha: float = 0.05) -> None:
        self.min_samples = min_samples
        self.significance_alpha = significance_alpha

    def analyze_paired_difference(
        self,
        baseline_values: list[float],
        candidate_values: list[float],
    ) -> tuple[bool, float | None, str]:
        """Calculates paired comparison p-value or returns INSUFFICIENT_SAMPLE."""
        n = min(len(baseline_values), len(candidate_values))
        if n < self.min_samples:
            return False, None, "INSUFFICIENT_SAMPLE"

        diffs = [candidate_values[i] - baseline_values[i] for i in range(n)]
        mean_diff = sum(diffs) / n
        variance = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1) if n > 1 else 0.0
        std_err = math.sqrt(variance / n) if variance > 0 else 0.0

        if std_err == 0.0:
            # Identical values or zero variance
            return False, 1.0, "ZERO_VARIANCE"

        # t-statistic approximation
        t_stat = mean_diff / std_err
        # Two-tailed p-value approximation using normal approximation for n >= 10
        # p ~ 2 * (1 - standard_normal_cdf(|t|))
        z = abs(t_stat)
        p_approx = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
        p_approx = max(0.0, min(1.0, p_approx))

        is_significant = p_approx < self.significance_alpha
        note = "STATISTICALLY_SIGNIFICANT" if is_significant else "NOT_SIGNIFICANT"
        return is_significant, p_approx, note


class RegressionService:
    """Detects multi-metric regressions, classifies severity, and identifies per-case diffs."""

    def __init__(
        self,
        repository: ContinuousEvaluationRepositoryProtocol,
        significance_analyzer: SignificanceAnalyzer | None = None,
        instrumentation: ContinuousEvaluationInstrumentation | None = None,
        severity_thresholds: dict[RegressionSeverity, float] | None = None,
    ) -> None:
        self.repository = repository
        self.significance_analyzer = significance_analyzer or SignificanceAnalyzer()
        self.instrumentation = instrumentation
        # Relative drop thresholds
        self.severity_thresholds = severity_thresholds or {
            RegressionSeverity.CRITICAL: 0.10,  # >= 10% drop
            RegressionSeverity.MAJOR: 0.05,  # >= 5% drop
            RegressionSeverity.WARNING: 0.03,  # >= 3% drop
            RegressionSeverity.INFO: 0.01,  # >= 1% drop
        }

    def classify_severity(self, relative_drop: float) -> RegressionSeverity | None:
        """Determines regression severity tier based on relative performance drop."""
        if relative_drop >= self.severity_thresholds[RegressionSeverity.CRITICAL]:
            return RegressionSeverity.CRITICAL
        if relative_drop >= self.severity_thresholds[RegressionSeverity.MAJOR]:
            return RegressionSeverity.MAJOR
        if relative_drop >= self.severity_thresholds[RegressionSeverity.WARNING]:
            return RegressionSeverity.WARNING
        if relative_drop >= self.severity_thresholds[RegressionSeverity.INFO]:
            return RegressionSeverity.INFO
        return None

    async def detect_regressions(
        self,
        *,
        benchmark_id: uuid.UUID,
        run_id: uuid.UUID,
        baseline_run_id: uuid.UUID,
        organization_id: uuid.UUID,
        baseline_metrics: dict[str, float],
        candidate_metrics: dict[str, float],
        baseline_results: list[EvaluationCaseResult] | None = None,
        candidate_results: list[EvaluationCaseResult] | None = None,
    ) -> list[RegressionFinding]:
        """Compares candidate run against baseline metrics and identifies case-level diffs."""
        findings: list[RegressionFinding] = []

        # Find per-case regressions
        case_diffs = self.compute_case_diffs(baseline_results or [], candidate_results or [])

        # Evaluate individual metrics
        for metric_name, b_val in baseline_metrics.items():
            if metric_name not in candidate_metrics:
                continue
            c_val = candidate_metrics[metric_name]

            # Direction: default is HIGHER_IS_BETTER
            # Latency / Cost are LOWER_IS_BETTER
            is_lower_better = any(
                term in metric_name.lower() for term in ["latency", "cost", "p95", "ms", "usd"]
            )

            if is_lower_better:
                # If candidate is higher than baseline, that's a degradation
                drop = ((c_val - b_val) / b_val) if b_val > 0 else 0.0
            else:
                drop = ((b_val - c_val) / b_val) if b_val > 0 else 0.0

            severity = self.classify_severity(drop)
            if severity:
                # Run statistical significance if results arrays are available
                b_series = self._extract_metric_series(baseline_results, metric_name)
                c_series = self._extract_metric_series(candidate_results, metric_name)
                is_sig, p_val, note = self.significance_analyzer.analyze_paired_difference(
                    b_series, c_series
                )

                finding = RegressionFinding(
                    benchmark_id=benchmark_id,
                    run_id=run_id,
                    baseline_run_id=baseline_run_id,
                    metric_name=metric_name,
                    baseline_value=float(b_val),
                    current_value=float(c_val),
                    drop_percentage=round(drop * 100.0, 2),
                    severity=severity,
                    details={"statistical_note": note, "is_lower_better": is_lower_better},
                    is_statistically_significant=is_sig,
                    p_value=p_val,
                    case_diffs=[d for d in case_diffs if metric_name in d.metric_changes],
                )
                findings.append(finding)

                if self.instrumentation:
                    self.instrumentation.record_regression_detected("end_to_end", severity.value)

        if findings:
            await self.repository.record_regressions(findings, organization_id)

        return findings

    def compute_case_diffs(
        self,
        baseline_results: list[EvaluationCaseResult],
        candidate_results: list[EvaluationCaseResult],
    ) -> list[CaseLevelDiff]:
        """Calculates case-level diffs detecting new failures, route regressions, and evidence drops."""
        diffs: list[CaseLevelDiff] = []
        b_map = {str(r.case_id): r for r in baseline_results}

        for c_res in candidate_results:
            cid = str(c_res.case_id)
            if cid not in b_map:
                continue
            b_res = b_map[cid]

            b_passed = b_res.passed
            c_passed = c_res.passed

            # Detect failure regression or route change
            b_route = (b_res.actual_route or "none").upper()
            c_route = (c_res.actual_route or "none").upper()
            route_changed = b_route != c_route

            if (b_passed and not c_passed) or route_changed:
                difficulty_str = getattr(c_res.case, "difficulty", "medium").upper()
                try:
                    difficulty = DifficultyLevel(difficulty_str)
                except ValueError:
                    difficulty = DifficultyLevel.MEDIUM

                metric_changes = {
                    "grounding_delta": (c_res.grounding_score or 0.0)
                    - (b_res.grounding_score or 0.0),
                    "sql_validity_delta": (1.0 if (c_res.sql_score or 0.0) > 0 else 0.0)
                    - (1.0 if (b_res.sql_score or 0.0) > 0 else 0.0),
                }

                diffs.append(
                    CaseLevelDiff(
                        case_id=cid,
                        query=getattr(c_res.case, "query", ""),
                        difficulty=difficulty,
                        baseline_status="PASS" if b_passed else "FAIL",
                        candidate_status="PASS" if c_passed else "FAIL",
                        reason=c_res.failure_reason
                        or ("Route mismatch" if route_changed else "Quality regression"),
                        metric_changes=metric_changes,
                        evidence_differences={
                            "baseline_evidence_count": len(
                                c_res.metrics_detail.get("evidence", [])
                            ),
                            "candidate_evidence_count": len(
                                b_res.metrics_detail.get("evidence", [])
                            ),
                        },
                        route_differences={"baseline_route": b_route, "candidate_route": c_route},
                    )
                )

        return diffs

    def _extract_metric_series(
        self, results: list[EvaluationCaseResult] | None, metric_name: str
    ) -> list[float]:
        """Extracts numerical series for statistical paired comparison."""
        if not results:
            return []
        series: list[float] = []
        for r in results:
            if "ground" in metric_name.lower():
                series.append(float(r.grounding_score or 0.0))
            elif "citation" in metric_name.lower():
                series.append(float(r.citation_score or 0.0))
            elif "sql" in metric_name.lower():
                series.append(float(r.sql_score or 0.0))
            else:
                series.append(1.0 if r.passed else 0.0)
        return series
