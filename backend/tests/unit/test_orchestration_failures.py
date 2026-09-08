"""Failure injection and degradation tests for Response Orchestration."""

from app.response_orchestration.application.decision_service import DecisionService
from app.response_orchestration.domain.enums import (
    ClaimStatus,
    DecisionType,
    EvidenceSourceType,
    EvidenceTrustLevel,
    ExecutionStrategy,
)
from app.response_orchestration.domain.models import (
    Claim,
    EvidenceBundle,
    EvidenceConflict,
    EvidenceItem,
    OrchestrationBudget,
    UnifiedReasoningPlan,
)


def test_missing_evidence_causes_insufficient_evidence_decision() -> None:
    """Verify empty evidence bundle results in INSUFFICIENT_EVIDENCE."""
    svc = DecisionService()
    plan = UnifiedReasoningPlan(
        intent="query",
        entities=[],
        resolved_metrics=[],
        resolved_dimensions=[],
        semantic_matches=[],
        graph_paths=[],
        candidate_datasets=[],
        execution_strategy=ExecutionStrategy.SQL_ONLY,
        budget=OrchestrationBudget(),
    )
    decision = svc.evaluate_decision(
        plan=plan,
        evidence_bundle=EvidenceBundle(items=[]),
        conflicts=[],
        claims=[],
        confidence_score=0.0,
        evidence_coverage=0.0,
    )
    assert decision == DecisionType.INSUFFICIENT_EVIDENCE


def test_branch_failure_causes_partial_answer() -> None:
    """Verify that a failure in one data branch downgrades decision to PARTIAL_ANSWER."""
    svc = DecisionService()
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                evidence_id="1",
                source_type=EvidenceSourceType.SQL,
                source_id="sql-1",
                content="SQL results intact.",
                trust_level=EvidenceTrustLevel.DIRECT,
                confidence=0.95,
                citation_id="[S1]",
            )
        ]
    )
    plan = UnifiedReasoningPlan(
        intent="query",
        entities=[],
        resolved_metrics=[],
        resolved_dimensions=[],
        semantic_matches=[],
        graph_paths=[],
        candidate_datasets=[],
        execution_strategy=ExecutionStrategy.HYBRID,
        budget=OrchestrationBudget(),
    )
    decision = svc.evaluate_decision(
        plan=plan,
        evidence_bundle=bundle,
        conflicts=[],
        claims=[],
        confidence_score=0.75,
        evidence_coverage=0.90,
        branch_failures=["RAG: connection timeout"],
    )
    assert decision == DecisionType.PARTIAL_ANSWER


def test_critical_conflict_triggers_warning_decision() -> None:
    """Verify that detected critical data conflicts trigger ANSWER_WITH_WARNING."""
    svc = DecisionService()
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                evidence_id="1",
                source_type=EvidenceSourceType.SQL,
                source_id="sql-1",
                content="Revenue $1M.",
                trust_level=EvidenceTrustLevel.DIRECT,
                confidence=0.95,
                citation_id="[S1]",
            )
        ]
    )
    conflict = EvidenceConflict(
        conflict_id="c1",
        field="revenue",
        source_a="SQL",
        value_a="$1,000,000",
        source_b="Doc",
        value_b="$1,500,000",
        severity="critical",
        description="Significant discrepancy",
    )
    plan = UnifiedReasoningPlan(
        intent="query",
        entities=[],
        resolved_metrics=[],
        resolved_dimensions=[],
        semantic_matches=[],
        graph_paths=[],
        candidate_datasets=[],
        execution_strategy=ExecutionStrategy.HYBRID,
        budget=OrchestrationBudget(),
    )
    decision = svc.evaluate_decision(
        plan=plan,
        evidence_bundle=bundle,
        conflicts=[conflict],
        claims=[],
        confidence_score=0.70,
        evidence_coverage=0.85,
    )
    assert decision == DecisionType.ANSWER_WITH_WARNING


def test_low_evidence_coverage_hallucination_gate() -> None:
    """Verify that low claim coverage blocks full answer."""
    svc = DecisionService()
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                evidence_id="1",
                source_type=EvidenceSourceType.SQL,
                source_id="sql-1",
                content="Only 1 claim supported.",
                trust_level=EvidenceTrustLevel.DIRECT,
                confidence=0.90,
                citation_id="[S1]",
            )
        ]
    )
    claims = [
        Claim(
            claim_id="1",
            statement="S1",
            required_evidence_type=None,
            citations_claimed=["[S1]"],
            status=ClaimStatus.SUPPORTED,
        ),
        Claim(
            claim_id="2",
            statement="S2",
            required_evidence_type=None,
            citations_claimed=[],
            status=ClaimStatus.UNSUPPORTED,
        ),
        Claim(
            claim_id="3",
            statement="S3",
            required_evidence_type=None,
            citations_claimed=[],
            status=ClaimStatus.UNSUPPORTED,
        ),
    ]
    plan = UnifiedReasoningPlan(
        intent="query",
        entities=[],
        resolved_metrics=[],
        resolved_dimensions=[],
        semantic_matches=[],
        graph_paths=[],
        candidate_datasets=[],
        execution_strategy=ExecutionStrategy.SQL_ONLY,
        budget=OrchestrationBudget(),
    )
    decision = svc.evaluate_decision(
        plan=plan,
        evidence_bundle=bundle,
        conflicts=[],
        claims=claims,
        confidence_score=0.50,
        evidence_coverage=0.33,
    )
    assert decision in (DecisionType.INSUFFICIENT_EVIDENCE, DecisionType.PARTIAL_ANSWER)
