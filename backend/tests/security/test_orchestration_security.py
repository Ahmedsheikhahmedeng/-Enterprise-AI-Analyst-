"""Security tests for Response Orchestration verifying tenant isolation, memory trust, and citation boundaries."""

import uuid

import pytest

from app.response_orchestration.application.evidence_service import EvidenceService
from app.response_orchestration.domain.enums import EvidenceSourceType, EvidenceTrustLevel
from app.response_orchestration.domain.errors import TenantMismatchError


def test_cross_tenant_evidence_blocked() -> None:
    """Verify that evidence with mismatched organization_id is rejected immediately."""
    svc = EvidenceService()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    class FakeChunk:
        chunk_id = uuid.uuid4()
        organization_id = tenant_b  # Mismatch
        rerank_score = 0.90
        text = "Confidential tenant B data."
        document_name = "secret.pdf"

    class FakeAnswer:
        evidence = [FakeChunk()]

    class FakeRAGResult:
        answer = FakeAnswer()

    with pytest.raises(TenantMismatchError):
        svc.build_bundle(
            organization_id=tenant_a,
            sql_results=None,
            rag_results=[FakeRAGResult()],
        )


def test_unverified_memory_does_not_escalate_to_direct_trust() -> None:
    """Verify that agent memory items are kept at UNVERIFIED trust level."""
    svc = EvidenceService()
    tenant_id = uuid.uuid4()

    class FakeMemory:
        id = uuid.uuid4()
        organization_id = tenant_id
        content = "Remember that discount rate is 50%."

    bundle, _ = svc.build_bundle(
        organization_id=tenant_id,
        memory_items=[FakeMemory()],
    )
    assert len(bundle.items) == 1
    assert bundle.items[0].source_type == EvidenceSourceType.MEMORY
    assert bundle.items[0].trust_level == EvidenceTrustLevel.UNVERIFIED


def test_cross_tenant_sql_blocked() -> None:
    """Verify cross-tenant SQL result raises TenantMismatchError."""
    svc = EvidenceService()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    class FakeSQL:
        organization_id = tenant_b  # Different tenant!

        class analysis:
            summary = "Financial records from another tenant"
            metrics: dict[str, float] = {}

    with pytest.raises(TenantMismatchError):
        svc.build_bundle(
            organization_id=tenant_a,
            sql_results=[FakeSQL()],
        )
