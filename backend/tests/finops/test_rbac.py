"""Tests for FinOps Role-Based Access Control (RBAC) permission matrices."""

from app.rbac.catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    PERM_FINOPS_ANOMALY_READ,
    PERM_FINOPS_BUDGET_MANAGE,
    PERM_FINOPS_BUDGET_READ,
    PERM_FINOPS_MANAGE,
    PERM_FINOPS_OPTIMIZATION_READ,
    PERM_FINOPS_POLICY_MANAGE,
    PERM_FINOPS_PRICING_MANAGE,
    PERM_FINOPS_QUOTA_MANAGE,
    PERM_FINOPS_READ,
    PERM_FINOPS_RECONCILIATION_READ,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_VIEWER,
)


def test_admin_role_has_all_finops_permissions() -> None:
    """Admin role must possess all 10 FinOps management and read permissions."""
    admin_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_ADMIN]
    expected_finops = [
        PERM_FINOPS_READ,
        PERM_FINOPS_MANAGE,
        PERM_FINOPS_BUDGET_READ,
        PERM_FINOPS_BUDGET_MANAGE,
        PERM_FINOPS_QUOTA_MANAGE,
        PERM_FINOPS_PRICING_MANAGE,
        PERM_FINOPS_ANOMALY_READ,
        PERM_FINOPS_POLICY_MANAGE,
        PERM_FINOPS_RECONCILIATION_READ,
        PERM_FINOPS_OPTIMIZATION_READ,
    ]
    for perm in expected_finops:
        assert perm in admin_perms, f"Admin role missing {perm}"


def test_analyst_role_finops_permissions() -> None:
    """Analyst role possesses operational read permissions but cannot modify budgets or pricing."""
    analyst_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_ANALYST]
    assert PERM_FINOPS_READ in analyst_perms
    assert PERM_FINOPS_BUDGET_READ in analyst_perms
    assert PERM_FINOPS_ANOMALY_READ in analyst_perms
    assert PERM_FINOPS_RECONCILIATION_READ in analyst_perms
    assert PERM_FINOPS_OPTIMIZATION_READ in analyst_perms

    # Mutating permissions forbidden for Analyst
    assert PERM_FINOPS_BUDGET_MANAGE not in analyst_perms
    assert PERM_FINOPS_PRICING_MANAGE not in analyst_perms
    assert PERM_FINOPS_QUOTA_MANAGE not in analyst_perms
    assert PERM_FINOPS_POLICY_MANAGE not in analyst_perms


def test_viewer_role_finops_permissions() -> None:
    """Viewer role only possesses basic read permissions and cannot alter financial configurations."""
    viewer_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_VIEWER]
    assert PERM_FINOPS_READ in viewer_perms
    assert PERM_FINOPS_BUDGET_READ in viewer_perms

    # Must NOT have write/manage permissions
    assert PERM_FINOPS_BUDGET_MANAGE not in viewer_perms
    assert PERM_FINOPS_PRICING_MANAGE not in viewer_perms
    assert PERM_FINOPS_QUOTA_MANAGE not in viewer_perms
    assert PERM_FINOPS_POLICY_MANAGE not in viewer_perms
