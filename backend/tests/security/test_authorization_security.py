"""Authorization & IDOR Security Tests — TASK 22.

Verifies:
- IDOR protection on direct object references (report_id, analysis_id, etc.)
- Resource ownership enforcement
- Rejection of mismatched user ownership
"""

import uuid
from dataclasses import dataclass

import pytest

from app.security.exceptions import IDORViolationError
from app.security.policies import TenantSecurityPolicy


@dataclass
class DummyReport:
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    title: str


@dataclass
class DummyAnalysis:
    id: uuid.UUID
    organization_id: uuid.UUID
    report_id: uuid.UUID
    user_id: uuid.UUID


def test_resource_ownership_permitted_for_owner() -> None:
    owner_id = uuid.uuid4()
    TenantSecurityPolicy.assert_resource_ownership(
        user_id=owner_id,
        resource_owner_id=owner_id,
        resource_type="report",
        resource_id=uuid.uuid4(),
    )


def test_resource_ownership_denied_for_different_user() -> None:
    legitimate_owner = uuid.uuid4()
    malicious_actor = uuid.uuid4()
    report_id = uuid.uuid4()

    with pytest.raises(IDORViolationError) as exc_info:
        TenantSecurityPolicy.assert_resource_ownership(
            user_id=malicious_actor,
            resource_owner_id=legitimate_owner,
            resource_type="report",
            resource_id=report_id,
        )
    assert "Ownership violation" in str(exc_info.value)


def test_nested_resource_idor_parent_child_mismatch() -> None:
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    report_a = DummyReport(
        id=uuid.uuid4(), organization_id=org_id, user_id=user_id, title="Report A"
    )
    report_b = DummyReport(
        id=uuid.uuid4(), organization_id=org_id, user_id=user_id, title="Report B"
    )

    # Analysis belongs to report_a, but caller attempts to bind with report_b
    analysis = DummyAnalysis(
        id=uuid.uuid4(), organization_id=org_id, report_id=report_a.id, user_id=user_id
    )

    # Legitimate binding succeeds
    TenantSecurityPolicy.assert_nested_ownership(
        parent_resource=report_a,
        child_resource=analysis,
        parent_id_attr="report_id",
        parent_type="report",
        child_type="analysis",
    )

    # Injected / hijacked binding raises IDORViolationError
    with pytest.raises(IDORViolationError) as exc_info:
        TenantSecurityPolicy.assert_nested_ownership(
            parent_resource=report_b,
            child_resource=analysis,
            parent_id_attr="report_id",
            parent_type="report",
            child_type="analysis",
        )
    assert "IDOR violation" in str(exc_info.value)
