"""RBAC module providing permissions catalog, role management, and authorization dependencies."""

from app.rbac.catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_VIEWER,
    SYSTEM_PERMISSIONS,
    SYSTEM_ROLES,
)
from app.rbac.dependencies import require_permission, resolve_organization_context
from app.rbac.repository import RBACRepository
from app.rbac.router import admin_router, rbac_router
from app.rbac.service import RBACService

__all__ = [
    "DEFAULT_ROLE_PERMISSIONS",
    "ROLE_ADMIN",
    "ROLE_ANALYST",
    "ROLE_VIEWER",
    "SYSTEM_PERMISSIONS",
    "SYSTEM_ROLES",
    "RBACRepository",
    "RBACService",
    "admin_router",
    "rbac_router",
    "require_permission",
    "resolve_organization_context",
]
