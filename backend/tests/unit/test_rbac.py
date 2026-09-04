"""Unit tests verifying RBAC permission catalog, role definitions, and schema contracts."""

from app.rbac.catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    PERM_AI_ANALYZE,
    PERM_AI_CHAT,
    PERM_ANALYTICS_EXECUTE,
    PERM_ANALYTICS_READ,
    PERM_AUDIT_READ,
    PERM_DATA_SOURCES_DELETE,
    PERM_DATA_SOURCES_READ,
    PERM_DATA_SOURCES_WRITE,
    PERM_DATASETS_DELETE,
    PERM_DATASETS_READ,
    PERM_DATASETS_WRITE,
    PERM_DOCUMENTS_DELETE,
    PERM_DOCUMENTS_MANAGE,
    PERM_DOCUMENTS_READ,
    PERM_DOCUMENTS_WRITE,
    PERM_ORGANIZATION_MANAGE,
    PERM_ORGANIZATION_READ,
    PERM_REPORTS_CREATE,
    PERM_REPORTS_DELETE,
    PERM_REPORTS_READ,
    PERM_REPORTS_UPDATE,
    PERM_USAGE_READ,
    PERM_USERS_INVITE,
    PERM_USERS_MANAGE,
    PERM_USERS_READ,
    PERM_USERS_REMOVE,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_VIEWER,
    SYSTEM_PERMISSIONS,
    SYSTEM_ROLES,
)


def test_permission_catalog_completeness() -> None:
    """Verify all 26 permissions are registered with descriptive metadata."""
    expected_permissions = {
        PERM_USERS_READ,
        PERM_USERS_MANAGE,
        PERM_USERS_INVITE,
        PERM_USERS_REMOVE,
        PERM_ORGANIZATION_READ,
        PERM_ORGANIZATION_MANAGE,
        PERM_DOCUMENTS_READ,
        PERM_DOCUMENTS_WRITE,
        PERM_DOCUMENTS_DELETE,
        PERM_DOCUMENTS_MANAGE,
        PERM_DATASETS_READ,
        PERM_DATASETS_WRITE,
        PERM_DATASETS_DELETE,
        PERM_DATA_SOURCES_READ,
        PERM_DATA_SOURCES_WRITE,
        PERM_DATA_SOURCES_DELETE,
        PERM_REPORTS_READ,
        PERM_REPORTS_CREATE,
        PERM_REPORTS_UPDATE,
        PERM_REPORTS_DELETE,
        PERM_ANALYTICS_READ,
        PERM_ANALYTICS_EXECUTE,
        PERM_AI_CHAT,
        PERM_AI_ANALYZE,
        PERM_AUDIT_READ,
        PERM_USAGE_READ,
    }
    assert set(SYSTEM_PERMISSIONS.keys()) == expected_permissions
    assert len(SYSTEM_PERMISSIONS) == 26
    for perm_name, desc in SYSTEM_PERMISSIONS.items():
        assert isinstance(perm_name, str) and "." in perm_name
        assert isinstance(desc, str) and len(desc) > 5


def test_system_roles_definitions() -> None:
    """Verify system role definitions exist for Admin, Analyst, and Viewer."""
    assert ROLE_ADMIN in SYSTEM_ROLES
    assert ROLE_ANALYST in SYSTEM_ROLES
    assert ROLE_VIEWER in SYSTEM_ROLES
    assert len(SYSTEM_ROLES) == 3


def test_admin_role_has_all_permissions() -> None:
    """Verify Admin role has all 26 system permissions without exception."""
    admin_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_ADMIN]
    assert admin_perms == set(SYSTEM_PERMISSIONS.keys())
    assert len(admin_perms) == 26


def test_analyst_role_permissions_matrix() -> None:
    """Verify Analyst role permissions match Task 5 specification."""
    analyst_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_ANALYST]

    # Required permissions for Analyst
    assert PERM_ORGANIZATION_READ in analyst_perms
    assert PERM_DOCUMENTS_READ in analyst_perms
    assert PERM_DOCUMENTS_WRITE in analyst_perms
    assert PERM_DATASETS_READ in analyst_perms
    assert PERM_DATASETS_WRITE in analyst_perms
    assert PERM_DATA_SOURCES_READ in analyst_perms
    assert PERM_REPORTS_READ in analyst_perms
    assert PERM_REPORTS_CREATE in analyst_perms
    assert PERM_ANALYTICS_READ in analyst_perms
    assert PERM_ANALYTICS_EXECUTE in analyst_perms
    assert PERM_AI_CHAT in analyst_perms
    assert PERM_AI_ANALYZE in analyst_perms

    # Denied permissions for Analyst
    assert PERM_USERS_MANAGE not in analyst_perms
    assert PERM_USERS_REMOVE not in analyst_perms
    assert PERM_DOCUMENTS_DELETE not in analyst_perms
    assert PERM_DOCUMENTS_MANAGE not in analyst_perms
    assert PERM_ORGANIZATION_MANAGE not in analyst_perms
    assert PERM_AUDIT_READ not in analyst_perms
    assert PERM_USAGE_READ not in analyst_perms


def test_viewer_role_permissions_matrix() -> None:
    """Verify Viewer role permissions match Task 5 specification."""
    viewer_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_VIEWER]

    # Required read permissions for Viewer
    assert PERM_ORGANIZATION_READ in viewer_perms
    assert PERM_DOCUMENTS_READ in viewer_perms
    assert PERM_DATASETS_READ in viewer_perms
    assert PERM_REPORTS_READ in viewer_perms
    assert PERM_ANALYTICS_READ in viewer_perms
    assert PERM_AI_CHAT in viewer_perms

    # Denied write/management/executive permissions for Viewer
    assert PERM_USERS_MANAGE not in viewer_perms
    assert PERM_DOCUMENTS_WRITE not in viewer_perms
    assert PERM_DOCUMENTS_DELETE not in viewer_perms
    assert PERM_DATASETS_WRITE not in viewer_perms
    assert PERM_REPORTS_CREATE not in viewer_perms
    assert PERM_ANALYTICS_EXECUTE not in viewer_perms
    assert PERM_AI_ANALYZE not in viewer_perms
    assert PERM_AUDIT_READ not in viewer_perms
