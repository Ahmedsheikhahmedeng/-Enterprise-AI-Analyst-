"""Release policy service enforcing governance approvals and blocking regressions."""

from app.continuous_evaluation.domain.enums import QualityGateDecision, ReleaseStatus
from app.continuous_evaluation.domain.errors import ReleaseBlockedError
from app.continuous_evaluation.domain.models import QualityGateResult
from app.observability.instrumentation.continuous_evaluation import (
    ContinuousEvaluationInstrumentation,
)


class ReleaseQualityPolicy:
    """Evaluates release readiness based on quality gate decisions, strictly prohibiting autonomous bypass."""

    def __init__(self, instrumentation: ContinuousEvaluationInstrumentation | None = None) -> None:
        self.instrumentation = instrumentation

    def evaluate_release_decision(
        self,
        gate_results: list[QualityGateResult],
        approver_is_agent: bool = False,
    ) -> tuple[ReleaseStatus, str]:
        """Determines whether a system release/model update is eligible for approval."""
        if approver_is_agent:
            raise ReleaseBlockedError(
                "Security violation: Autonomous agents cannot approve release decisions"
            )

        if not gate_results:
            return (
                ReleaseStatus.PENDING,
                "No quality gate evaluations found; release cannot proceed",
            )

        # Check for BLOCK_RELEASE or FAIL
        for res in gate_results:
            if res.decision == QualityGateDecision.BLOCK_RELEASE:
                reason = f"Critical quality gate {res.gate_id} produced BLOCK_RELEASE with {len(res.violations)} violations"
                if self.instrumentation:
                    self.instrumentation.record_quality_gate_result(
                        "block_release", "release_policy"
                    )
                return ReleaseStatus.REJECTED, reason

            if res.decision == QualityGateDecision.FAIL:
                reason = f"Quality gate {res.gate_id} failed threshold criteria"
                return ReleaseStatus.REJECTED, reason

        # All passed or warned
        has_warnings = any(r.decision == QualityGateDecision.WARN for r in gate_results)
        msg = (
            "Release approved with warnings"
            if has_warnings
            else "Release approved: All quality gates passed"
        )
        return ReleaseStatus.APPROVED, msg

    def enforce_release(
        self,
        gate_results: list[QualityGateResult],
        approver_is_agent: bool = False,
    ) -> None:
        """Enforces release policy and raises ReleaseBlockedError if conditions are not met."""
        status, reason = self.evaluate_release_decision(
            gate_results, approver_is_agent=approver_is_agent
        )
        if status == ReleaseStatus.REJECTED:
            raise ReleaseBlockedError(f"Release blocked by quality policy: {reason}")
