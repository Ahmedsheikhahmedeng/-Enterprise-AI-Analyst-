"""Multi-Tenant Isolation Security Tests — TASK 22.

Verifies:
- Strict rejection of cross-tenant resource access
- Nested resource cross-tenant access rejection (Org A user -> Org B report/analysis)
- TenantContext integrity
"""

import uuid
from dataclasses import dataclass

import pytest

from app.security.context import SecurityContext
from app.security.exceptions import TenantIsolationViolationError
from app.security.policies import TenantSecurityPolicy


@dataclass
class MockTenantEntity:
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    parent_id: uuid.UUID | None = None


def test_same_tenant_access_allowed() -> None:
    org_id = uuid.uuid4()
    context = SecurityContext(
        user_id=str(uuid.uuid4()),
        organization_id=str(org_id),
        roles=["analyst"],
    )
    resource = MockTenantEntity(id=uuid.uuid4(), organization_id=org_id, title="Quarterly Metrics")

    # Should not raise
    TenantSecurityPolicy.require_tenant_resource(
        context=context,
        resource=resource,
        resource_type="report",
    )


def test_cross_tenant_access_strictly_rejected() -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    user_a_context = SecurityContext(
        user_id=str(uuid.uuid4()),
        organization_id=str(org_a),
        roles=["analyst"],
    )
    resource_b = MockTenantEntity(
        id=uuid.uuid4(),
        organization_id=org_b,
        title="Confidential Financial Plan",
    )

    with pytest.raises(TenantIsolationViolationError) as exc_info:
        TenantSecurityPolicy.require_tenant_resource(
            context=user_a_context,
            resource=resource_b,
            resource_type="report",
        )

    assert "Cross-tenant access violation" in str(exc_info.value)
    assert str(org_a) in str(exc_info.value)
    assert str(org_b) in str(exc_info.value)


def test_missing_tenant_context_rejected() -> None:
    resource = MockTenantEntity(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        title="Tenant Document",
    )
    unauthenticated_context = SecurityContext(
        user_id=None,
        organization_id=None,
    )

    with pytest.raises(TenantIsolationViolationError) as exc_info:
        TenantSecurityPolicy.require_tenant_resource(
            context=unauthenticated_context,
            resource=resource,
            resource_type="document",
        )
    assert "Missing or unauthenticated tenant context" in str(exc_info.value)


def test_nested_resource_cross_tenant_mismatch() -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    parent_a = MockTenantEntity(id=uuid.uuid4(), organization_id=org_a, title="Parent Org A")
    child_b = MockTenantEntity(id=uuid.uuid4(), organization_id=org_b, title="Child Org B")
    child_b.parent_id = parent_a.id

    with pytest.raises(TenantIsolationViolationError) as exc_info:
        TenantSecurityPolicy.assert_nested_ownership(
            parent_resource=parent_a,
            child_resource=child_b,
            parent_id_attr="parent_id",
            parent_type="report",
            child_type="analysis",
        )
    assert "cross-tenant mismatch" in str(exc_info.value)
