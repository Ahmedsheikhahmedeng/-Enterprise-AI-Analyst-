"""Unit tests validating strict multi-tenant isolation across all compliance entities."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.models import (
    ComplianceControl,
    ComplianceEvidence,
    LegalHold,
    SecurityFinding,
)
from app.compliance.service import ComplianceService


@pytest.mark.asyncio
async def test_tenant_isolation_evidence_and_findings(db_session: AsyncSession) -> None:
    service = ComplianceService(db_session)
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    # Ensure parent control exists
    ctrl = await service.repo.get_control("ctrl-auth-001")
    if not ctrl:
        ctrl = ComplianceControl(
            id="ctrl-auth-001",
            framework="INTERNAL_SECURITY_BASELINE",
            control_code="SEC-AUTH-001",
            name="Password Hashing & Strength Policy",
            description="Argon2id hashing with minimum 12 chars and entropy checks.",
            category="AUTHENTICATION",
            severity="HIGH",
            automated=True,
            enabled=True,
        )
        await service.repo.save_control(ctrl)

    # Evidence in Tenant A
    ev_a = ComplianceEvidence(
        id=str(uuid.uuid4()),
        control_id="ctrl-auth-001",
        organization_id=org_a,
        evidence_type="SECURITY_TEST",
        source="scanner",
        reference="ref-a",
        hash="hash_a",
        captured_at=datetime.now(UTC),
    )
    await service.repo.save_evidence(ev_a)

    # Finding in Tenant B
    finding_b = SecurityFinding(
        id=str(uuid.uuid4()),
        organization_id=org_b,
        severity="HIGH",
        status="OPEN",
        title="Tenant B Finding",
        description="Private to B",
        source="scanner",
    )
    await service.repo.save_finding(finding_b)

    # Tenant B querying evidence -> cannot see Tenant A's evidence
    evidence_b = await service.repo.list_evidence(organization_id=org_b)
    assert not any(e.id == ev_a.id for e in evidence_b)

    # Tenant A querying findings -> cannot see Tenant B's finding
    findings_a = await service.repo.list_findings(organization_id=org_a)
    assert not any(f.id == finding_b.id for f in findings_a)


@pytest.mark.asyncio
async def test_tenant_isolation_retention_and_legal_holds(db_session: AsyncSession) -> None:
    service = ComplianceService(db_session)
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    hold_a = LegalHold(
        id=str(uuid.uuid4()),
        organization_id=org_a,
        name="Hold A",
        reason="Preservation A",
        created_by="admin_a",
        active=True,
        starts_at=datetime.now(UTC),
        resources=["*"],
    )
    await service.repo.save_legal_hold(hold_a)

    # Tenant B querying active legal holds -> sees none
    holds_b = await service.repo.list_active_legal_holds(org_b)
    assert not any(h.id == hold_a.id for h in holds_b)
