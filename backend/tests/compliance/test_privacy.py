"""Unit tests for Privacy Requests and Right-to-Delete governed execution."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.enums import PrivacyRequestStatus, PrivacyRequestType
from app.compliance.exceptions import ComplianceError
from app.compliance.models import LegalHold
from app.compliance.service import ComplianceService


@pytest.mark.asyncio
async def test_privacy_request_creation_and_execution(db_session: AsyncSession) -> None:
    service = ComplianceService(db_session)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 1. Create deletion request
    req = await service.create_privacy_request(
        organization_id=org_id,
        user_id=user_id,
        request_type=PrivacyRequestType.RIGHT_TO_DELETE,
        requested_by="user@domain.com",
        resources=["documents", "memory"],
        notes="GDPR erasure request",
    )
    assert req.status == PrivacyRequestStatus.REQUESTED
    assert req.request_type == PrivacyRequestType.RIGHT_TO_DELETE

    # 2. Execute deletion request with governance approval
    executed = await service.execute_privacy_request(
        request_id=req.id,
        organization_id=org_id,
        governance_approval_id="gov-appr-4412",
    )
    assert executed.status == PrivacyRequestStatus.EXECUTED
    assert executed.governance_approval_id == "gov-appr-4412"
    assert executed.executed_at is not None


@pytest.mark.asyncio
async def test_privacy_deletion_blocked_by_legal_hold(db_session: AsyncSession) -> None:
    service = ComplianceService(db_session)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Active legal hold on tenant
    hold = LegalHold(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name="SEC Investigation",
        reason="Preserve all user files",
        created_by="legal@enterprise.com",
        active=True,
        starts_at=datetime.now(UTC),
        resources=["*"],
    )
    await service.repo.save_legal_hold(hold)

    req = await service.create_privacy_request(
        organization_id=org_id,
        user_id=user_id,
        request_type=PrivacyRequestType.RIGHT_TO_DELETE,
        requested_by="user@domain.com",
        resources=["documents"],
    )

    with pytest.raises(ComplianceError) as exc_info:
        await service.execute_privacy_request(
            request_id=req.id,
            organization_id=org_id,
            governance_approval_id="gov-appr-4412",
        )
    assert "legal hold" in str(exc_info.value).lower()
