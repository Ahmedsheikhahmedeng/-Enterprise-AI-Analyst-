"""Unit tests for Enterprise Response Orchestration components and state machine."""

import uuid

import pytest

from app.response_orchestration.application.confidence_service import ConfidenceService
from app.response_orchestration.application.conflict_service import ConflictService
from app.response_orchestration.application.decision_service import DecisionService
from app.response_orchestration.application.evidence_service import EvidenceService
from app.response_orchestration.application.verification_service import VerificationService
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
    EvidenceItem,
    OrchestrationBudget,
    UnifiedReasoningPlan,
)


@pytest.fixture
def sample_org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def evidence_bundle(sample_org_id: uuid.UUID) -> EvidenceBundle:
    items = [
        EvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.SQL,
            source_id="sales_table",
            content="Total revenue reached $1,500,000 in Q3 2026.",
            trust_level=EvidenceTrustLevel.DIRECT,
            confidence=0.98,
            is_calculated=True,
            citation_id="[S1]",
            metadata={"metrics": {"revenue": 1500000.0}},
        ),
        EvidenceItem(
            evidence_id="ev-2",
            source_type=EvidenceSourceType.DOCUMENT,
            source_id="financial_report.pdf",
            content="Q3 financial report confirmed revenue was approximately $1,500,000.",
            trust_level=EvidenceTrustLevel.DIRECT,
            confidence=0.92,
            is_calculated=False,
            citation_id="[D1]",
            metadata={"document_name": "financial_report.pdf"},
        ),
        EvidenceItem(
            evidence_id="ev-3",
            source_type=EvidenceSourceType.SEMANTIC,
            source_id="term-revenue",
            content="Approved Metric 'Revenue' defined as SUM(order_items.amount).",
            trust_level=EvidenceTrustLevel.DIRECT,
            confidence=0.95,
            is_calculated=False,
            citation_id="[M1]",
        ),
    ]
    return EvidenceBundle(items=items)


def test_confidence_scoring(evidence_bundle: EvidenceBundle) -> None:
    """Verify calibrated confidence calculation."""
    svc = ConfidenceService()
    claims = [
        Claim(
            claim_id="cl-1",
            statement="Revenue reached 1.5M in Q3.",
            required_evidence_type=EvidenceSourceType.SQL,
            citations_claimed=["[S1]"],
            status=ClaimStatus.SUPPORTED,
        ),
        Claim(
            claim_id="cl-2",
            statement="Revenue is calculated via sum of order items.",
            required_evidence_type=EvidenceSourceType.SEMANTIC,
            citations_claimed=["[M1]"],
            status=ClaimStatus.SUPPORTED,
        ),
    ]
    score = svc.calculate_confidence(
        evidence_bundle=evidence_bundle,
        conflicts=[],
        claims=claims,
        semantic_confidence=0.95,
        graph_confidence=0.80,
    )
    assert 0.85 <= score <= 1.0


def test_conflict_detection_mismatch(sample_org_id: uuid.UUID) -> None:
    """Verify ConflictService identifies discrepancy between SQL and document numbers."""
    svc = ConflictService()
    bundle = EvidenceBundle(
        items=[
            EvidenceItem(
                evidence_id="sql-1",
                source_type=EvidenceSourceType.SQL,
                source_id="orders",
                content="Net revenue calculated as $1,200,000.",
                trust_level=EvidenceTrustLevel.DIRECT,
                confidence=0.99,
                is_calculated=True,
                citation_id="[S1]",
                metadata={"metrics": {"revenue": 1200000.0}},
            ),
            EvidenceItem(
                evidence_id="doc-1",
                source_type=EvidenceSourceType.DOCUMENT,
                source_id="doc.pdf",
                content="Preliminary estimates put net revenue at $1,450,000.",
                trust_level=EvidenceTrustLevel.DIRECT,
                confidence=0.88,
                is_calculated=False,
                citation_id="[D1]",
            ),
        ]
    )
    conflicts = svc.detect_conflicts(bundle)
    assert len(conflicts) >= 1
    assert "1,200,000" in conflicts[0].value_a
    assert "1,450,000" in conflicts[0].value_b
    assert conflicts[0].severity in ("high", "medium")


def test_citation_validator_repair(evidence_bundle: EvidenceBundle) -> None:
    """Verify phantom citations are automatically stripped from response text."""
    svc = VerificationService()
    raw_text = "Revenue was $1.5M [S1] according to the report [D1] and unverified blog [D99]."
    clean_text, citations = svc.validate_and_repair_citations(raw_text, evidence_bundle)
    assert "[D99]" not in clean_text
    assert "[S1]" in clean_text
    assert "[D1]" in clean_text
    assert citations == ["[D1]", "[S1]"]


def test_claim_extraction_and_coverage(evidence_bundle: EvidenceBundle) -> None:
    """Verify claims are extracted and scored for evidence support."""
    svc = VerificationService()
    text = "Revenue reached $1.5M [S1]. Customer growth increased by 40% [D99]."
    claims, coverage = svc.extract_and_verify_claims(text, evidence_bundle)
    assert len(claims) == 2
    assert claims[0].status == ClaimStatus.SUPPORTED
    assert claims[1].status == ClaimStatus.UNSUPPORTED
    assert coverage == 0.5


def test_decision_service_logic(evidence_bundle: EvidenceBundle) -> None:
    """Verify decision rules emit proper DecisionType."""
    svc = DecisionService()
    plan = UnifiedReasoningPlan(
        intent="query",
        entities=[],
        resolved_metrics=["revenue"],
        resolved_dimensions=[],
        semantic_matches=[],
        graph_paths=[],
        candidate_datasets=[],
        execution_strategy=ExecutionStrategy.SQL_ONLY,
        budget=OrchestrationBudget(),
    )

    claims = [
        Claim(
            claim_id="1",
            statement="Stmt 1",
            required_evidence_type=None,
            citations_claimed=["[S1]"],
            status=ClaimStatus.SUPPORTED,
        ),
    ]

    decision = svc.evaluate_decision(
        plan=plan,
        evidence_bundle=evidence_bundle,
        conflicts=[],
        claims=claims,
        confidence_score=0.92,
        evidence_coverage=1.0,
    )
    assert decision == DecisionType.ANSWER


def test_decision_service_clarification() -> None:
    """Verify ambiguous plan triggers ASK_CLARIFICATION."""
    svc = DecisionService()
    plan = UnifiedReasoningPlan(
        intent="query",
        entities=[],
        resolved_metrics=["revenue", "gross_margin", "ebitda"],
        resolved_dimensions=[],
        semantic_matches=[],
        graph_paths=[],
        candidate_datasets=[],
        execution_strategy=ExecutionStrategy.HYBRID,
        budget=OrchestrationBudget(),
        requires_clarification=True,
        clarification_options=["revenue", "gross_margin"],
    )
    decision = svc.evaluate_decision(
        plan=plan,
        evidence_bundle=EvidenceBundle(),
        conflicts=[],
        claims=[],
        confidence_score=0.40,
        evidence_coverage=0.0,
    )
    assert decision == DecisionType.ASK_CLARIFICATION


def test_evidence_service_bundle_builder(sample_org_id: uuid.UUID) -> None:
    """Verify EvidenceService builds unified bundle with normalized [D#], [S#] tags."""
    svc = EvidenceService()

    class FakeSQL:
        datasource_id = uuid.uuid4()

        class analysis:
            summary = "Computed total active clients: 4,500."
            metrics = {"clients": 4500}

    bundle, citations = svc.build_bundle(
        organization_id=sample_org_id,
        sql_results=[FakeSQL()],
        rag_results=None,
    )
    assert len(bundle.items) == 1
    assert bundle.items[0].citation_id == "[S1]"
    assert citations[0].citation_id == "[S1]"
    assert bundle.has_authoritative_sql() is True
