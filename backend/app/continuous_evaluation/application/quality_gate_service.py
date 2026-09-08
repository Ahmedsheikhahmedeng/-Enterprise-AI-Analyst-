"""Quality Gate evaluation service enforcing non-negotiable standards for release readiness."""

import uuid
from typing import Any

from app.continuous_evaluation.domain.enums import QualityGateDecision, RegressionSeverity
from app.continuous_evaluation.domain.errors import QualityGateNotFoundError
from app.continuous_evaluation.domain.models import (
    QualityGateResult,
    QualityGateRule,
    RegressionFinding,
)
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol
from app.observability.instrumentation.continuous_evaluation import (
    ContinuousEvaluationInstrumentation,
)


class QualityGateService:
    """Evaluates benchmark runs against configurable quality gates and determines deployment decisions."""

    def __init__(
        self,
        repository: ContinuousEvaluationRepositoryProtocol,
        instrumentation: ContinuousEvaluationInstrumentation | None = None,
    ) -> None:
        self.repository = repository
        self.instrumentation = instrumentation

    async def create_gate(
        self,
        organization_id: uuid.UUID,
        name: str,
        rules: list[QualityGateRule],
        description: str | None = None,
    ) -> uuid.UUID:
        """Creates a quality gate with serializable rules."""
        rules_dict = {"rules": [r.to_dict() for r in rules]}
        return await self.repository.create_quality_gate(
            organization_id=organization_id,
            name=name,
            rules=rules_dict,
            description=description,
        )

    async def get_gate(self, gate_id: uuid.UUID, organization_id: uuid.UUID) -> dict[str, Any]:
        """Retrieves quality gate configuration."""
        gate = await self.repository.get_quality_gate(gate_id, organization_id)
        if not gate:
            raise QualityGateNotFoundError(f"Quality gate {gate_id} not found")
        return gate

    async def list_gates(self, organization_id: uuid.UUID) -> list[dict[str, Any]]:
        """Lists all quality gates in tenant scope."""
        return await self.repository.list_quality_gates(organization_id)

    async def evaluate_gate(
        self,
        gate_id: uuid.UUID,
        run_id: uuid.UUID,
        scorecard: dict[str, Any],
        organization_id: uuid.UUID,
        regressions: list[RegressionFinding] | None = None,
    ) -> QualityGateResult:
        """Evaluates scorecard metrics and regression findings against quality gate rules."""
        gate = await self.get_gate(gate_id, organization_id)
        rules_data = gate.get("rules", {}).get("rules", [])
        violations: list[dict[str, Any]] = []

        metrics = scorecard.get("metrics", {})
        segmented = scorecard.get("segmented_scores", {})
        combined_metrics = {**metrics, **segmented}

        # Also pull from composite quality if available
        if "composite_quality" in scorecard:
            combined_metrics.update(scorecard["composite_quality"].get("breakdown", {}))
            combined_metrics["overall_score"] = scorecard["composite_quality"].get(
                "overall_score", 0.0
            )

        critical_violation_found = False
        non_critical_violation_found = False

        for r_dict in rules_data:
            metric_name = r_dict.get("metric_name", "")
            min_th = r_dict.get("min_threshold")
            max_th = r_dict.get("max_threshold")
            max_drop_pct = r_dict.get("max_drop_percentage")
            is_critical = r_dict.get("is_critical", False)

            # Check threshold breaches
            if metric_name in combined_metrics:
                val = float(combined_metrics[metric_name])
                if min_th is not None and val < min_th:
                    violations.append(
                        {
                            "metric": metric_name,
                            "type": "MIN_THRESHOLD_BREACH",
                            "actual": val,
                            "expected_min": min_th,
                            "is_critical": is_critical,
                        }
                    )
                    if is_critical:
                        critical_violation_found = True
                    else:
                        non_critical_violation_found = True

                if max_th is not None and val > max_th:
                    violations.append(
                        {
                            "metric": metric_name,
                            "type": "MAX_THRESHOLD_BREACH",
                            "actual": val,
                            "expected_max": max_th,
                            "is_critical": is_critical,
                        }
                    )
                    if is_critical:
                        critical_violation_found = True
                    else:
                        non_critical_violation_found = True

            # Check regression drops
            if max_drop_pct is not None and regressions:
                for reg in regressions:
                    if reg.metric_name == metric_name and reg.drop_percentage > max_drop_pct:
                        violations.append(
                            {
                                "metric": metric_name,
                                "type": "REGRESSION_DROP_BREACH",
                                "actual_drop": reg.drop_percentage,
                                "max_allowed_drop": max_drop_pct,
                                "is_critical": is_critical,
                            }
                        )
                        if is_critical:
                            critical_violation_found = True
                        else:
                            non_critical_violation_found = True

        # Check for unhandled critical regressions even if not explicitly in rules
        if regressions:
            for reg in regressions:
                if reg.severity == RegressionSeverity.CRITICAL:
                    critical_violation_found = True
                    violations.append(
                        {
                            "metric": reg.metric_name,
                            "type": "CRITICAL_REGRESSION_SEVERITY",
                            "drop_percentage": reg.drop_percentage,
                            "is_critical": True,
                        }
                    )

        # Decide outcome
        if critical_violation_found:
            decision = QualityGateDecision.BLOCK_RELEASE
        elif non_critical_violation_found:
            decision = QualityGateDecision.FAIL
        else:
            decision = QualityGateDecision.PASS

        result = QualityGateResult(
            gate_id=gate_id,
            run_id=run_id,
            decision=decision,
            scorecard=scorecard,
            violations=violations,
        )

        await self.repository.record_quality_gate_result(result, organization_id)

        # Observability
        if self.instrumentation:
            self.instrumentation.record_quality_gate_result(decision.value, "gate_evaluation")

        return result
