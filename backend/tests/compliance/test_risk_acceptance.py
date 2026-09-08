"""Unit tests for Risk Acceptance workflows and privileged approval requirements."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.enums import FindingSeverity, FindingStatus
from app.compliance.exceptions import UnapprovedRiskAcceptanceError
from app.compliance.models import SecurityFinding
from app.compliance.service import ComplianceService


@pytest.mark.asyncio
async def test_critical_finding_requires_privileged_approval(db_session: AsyncSession) -> None:
    service = ComplianceService(db_session)
    org_id = uuid.uuid4()

    finding = SecurityFinding(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        severity=FindingSeverity.CRITICAL.value,
        status=FindingStatus.OPEN.value,
        title="Critical Vulnerability",
        description="Severe issue",
        source="scanner",
    )
    await service.repo.save_finding(finding)

    # Attempting acceptance without privileged approval must fail
    with pytest.raises(UnapprovedRiskAcceptanceError):
        await service.accept_finding_risk(
            finding_id=finding.id,
            reason="Business justification",
            expires_at=datetime.now(UTC) + timedelta(days=30),
            accepted_by="analyst@enterprise.com",
            organization_id=org_id,
            privileged_approval_id=None,
        )


@pytest.mark.asyncio
async def test_critical_finding_accepted_with_privileged_approval(db_session: AsyncSession) -> None:
    service = ComplianceService(db_session)
    org_id = uuid.uuid4()

    finding = SecurityFinding(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        severity=FindingSeverity.CRITICAL.value,
        status=FindingStatus.OPEN.value,
        title="Critical Vulnerability",
        description="Severe issue",
        source="scanner",
    )
    await service.repo.save_finding(finding)

    res = await service.accept_finding_risk(
        finding_id=finding.id,
        reason="Compensating firewall controls in place",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        accepted_by="ciso@enterprise.com",
        organization_id=org_id,
        privileged_approval_id="appr-gov-88712",
    )
    assert res.finding_id == finding.id
    assert res.privileged_approval_id == "appr-gov-88712"
    assert res.is_expired is False

    # Check updated status on finding
    updated = await service.repo.get_finding(finding.id, org_id)
    assert updated is not None
    assert updated.status == FindingStatus.ACCEPTED_RISK.value
