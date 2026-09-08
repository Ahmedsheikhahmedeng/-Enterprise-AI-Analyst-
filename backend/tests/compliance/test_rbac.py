"""Unit tests for RBAC enforcement on compliance operations."""

from app.rbac.catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    PERM_COMPLIANCE_ACCESS_REVIEW,
    PERM_COMPLIANCE_ASSESS,
    PERM_COMPLIANCE_EVIDENCE_MANAGE,
    PERM_COMPLIANCE_EVIDENCE_READ,
    PERM_COMPLIANCE_FINDINGS_READ,
    PERM_COMPLIANCE_MANAGE,
    PERM_COMPLIANCE_PRIVACY_MANAGE,
    PERM_COMPLIANCE_READ,
    PERM_COMPLIANCE_RETENTION_MANAGE,
    PERM_COMPLIANCE_RISK_ACCEPTANCE,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_VIEWER,
)


def test_viewer_role_compliance_restrictions() -> None:
    viewer_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_VIEWER]

    # Allowed read permissions
    assert PERM_COMPLIANCE_READ in viewer_perms
    assert PERM_COMPLIANCE_EVIDENCE_READ in viewer_perms
    assert PERM_COMPLIANCE_FINDINGS_READ in viewer_perms

    # Disallowed mutation permissions
    assert PERM_COMPLIANCE_MANAGE not in viewer_perms
    assert PERM_COMPLIANCE_RISK_ACCEPTANCE not in viewer_perms
    assert PERM_COMPLIANCE_PRIVACY_MANAGE not in viewer_perms
    assert PERM_COMPLIANCE_RETENTION_MANAGE not in viewer_perms
    assert PERM_COMPLIANCE_ACCESS_REVIEW not in viewer_perms
    assert PERM_COMPLIANCE_EVIDENCE_MANAGE not in viewer_perms


def test_analyst_role_compliance_permissions() -> None:
    analyst_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_ANALYST]
    assert PERM_COMPLIANCE_READ in analyst_perms
    assert PERM_COMPLIANCE_ASSESS in analyst_perms
    assert PERM_COMPLIANCE_FINDINGS_READ in analyst_perms
    assert PERM_COMPLIANCE_RISK_ACCEPTANCE not in analyst_perms


def test_admin_role_has_all_compliance_permissions() -> None:
    admin_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_ADMIN]
    assert PERM_COMPLIANCE_READ in admin_perms
    assert PERM_COMPLIANCE_MANAGE in admin_perms
    assert PERM_COMPLIANCE_ASSESS in admin_perms
    assert PERM_COMPLIANCE_RISK_ACCEPTANCE in admin_perms
    assert PERM_COMPLIANCE_PRIVACY_MANAGE in admin_perms
