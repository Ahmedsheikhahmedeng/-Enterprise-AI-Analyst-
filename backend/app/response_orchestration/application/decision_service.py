"""Decision Service evaluating completeness, conflicts, confidence, and generating actionable outcomes."""

import logging

from app.response_orchestration.domain.enums import DecisionType
from app.response_orchestration.domain.models import (
    Claim,
    EvidenceBundle,
    EvidenceConflict,
    UnifiedReasoningPlan,
)
from app.response_orchestration.domain.protocols import DecisionServiceProtocol

logger = logging.getLogger(__name__)


class DecisionService(DecisionServiceProtocol):
    """Determines final analytical decision based on evidence verification and policy invariants."""

    # Thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.75
    MEDIUM_CONFIDENCE_THRESHOLD = 0.50
    MIN_EVIDENCE_COVERAGE = 0.65

    def evaluate_decision(
        self,
        plan: UnifiedReasoningPlan,
        evidence_bundle: EvidenceBundle,
        conflicts: list[EvidenceConflict],
        claims: list[Claim],
        confidence_score: float,
        evidence_coverage: float,
        branch_failures: list[str] | None = None,
    ) -> DecisionType:
        """Derive authoritative analytical decision."""
        # 1. Ambiguity clarification request
        if plan.requires_clarification:
            return DecisionType.ASK_CLARIFICATION

        # 2. Complete absence of evidence
        if not evidence_bundle.items:
            return DecisionType.INSUFFICIENT_EVIDENCE

        # 3. Critical conflict detection
        has_critical_conflict = any(c.severity in ("critical", "high") for c in conflicts)

        # 4. Branch execution degradation
        has_failures = bool(branch_failures)

        # 5. Hallucination check / insufficient evidence coverage
        if claims and evidence_coverage < self.MIN_EVIDENCE_COVERAGE:
            if has_failures or len(evidence_bundle.items) < 2:
                return DecisionType.INSUFFICIENT_EVIDENCE
            return DecisionType.PARTIAL_ANSWER

        # 6. Branch failure handling
        if has_failures:
            return DecisionType.PARTIAL_ANSWER

        # 7. Confidence & Conflict evaluation
        if has_critical_conflict:
            return DecisionType.ANSWER_WITH_WARNING

        if confidence_score >= self.HIGH_CONFIDENCE_THRESHOLD:
            return DecisionType.ANSWER

        if confidence_score >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            return DecisionType.ANSWER_WITH_WARNING

        # Low confidence fallback
        return DecisionType.PARTIAL_ANSWER
