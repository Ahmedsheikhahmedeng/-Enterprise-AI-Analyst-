"""Tenant Isolation & Resource Authorization Policies — TASK 22.

Provides centralized policies for:
1. Multi-tenant isolation enforcement
2. IDOR (Insecure Direct Object Reference) prevention
3. Nested resource ownership verification (e.g. Org A -> Report A -> Analysis A)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.security.context import SecurityContext
from app.security.exceptions import IDORViolationError, TenantIsolationViolationError


class TenantSecurityPolicy:
    """Central policy engine for tenant isolation and resource access authorization."""

    @staticmethod
    def normalize_id(identifier: str | UUID | None) -> str | None:
        """Normalize UUID or string identifier for safe constant-time or exact comparison."""
        if identifier is None:
            return None
        return str(identifier).strip().lower()

    @classmethod
    def assert_same_tenant(
        cls,
        context_org_id: str | UUID | None,
        resource_org_id: str | UUID | None,
        resource_type: str = "resource",
        resource_id: str | UUID | None = None,
    ) -> None:
        """Assert that the requester's tenant matches the resource's owning tenant.

        Raises:
            TenantIsolationViolationError if organization IDs do not match or are missing.
        """
        ctx_org = cls.normalize_id(context_org_id)
        res_org = cls.normalize_id(resource_org_id)

        if not ctx_org:
            raise TenantIsolationViolationError(
                "Access denied: Missing or unauthenticated tenant context."
            )

        if not res_org:
            raise TenantIsolationViolationError(
                f"Access denied: Target {resource_type} has no associated tenant."
            )

        if ctx_org != res_org:
            res_id_str = f" id='{resource_id}'" if resource_id else ""
            raise TenantIsolationViolationError(
                f"Cross-tenant access violation: Tenant '{ctx_org}' attempted to access "
                f"{resource_type}{res_id_str} belonging to tenant '{res_org}'."
            )

    @classmethod
    def require_tenant_resource(
        cls,
        context: SecurityContext,
        resource: Any,
        resource_type: str = "resource",
    ) -> None:
        """Verify that an entity retrieved from database belongs to the current tenant."""
        resource_org_id = getattr(resource, "organization_id", None)
        resource_id = getattr(resource, "id", None)

        cls.assert_same_tenant(
            context_org_id=context.organization_id,
            resource_org_id=resource_org_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    @classmethod
    def assert_nested_ownership(
        cls,
        parent_resource: Any,
        child_resource: Any,
        parent_id_attr: str,
        parent_type: str = "parent",
        child_type: str = "child",
    ) -> None:
        """Verify nested resource hierarchy ownership.

        For example: An Analysis belongs to Report A in Org A.
        A user must not be able to cross-reference Report B in Org B with Analysis A.
        """
        # 1. Assert tenant match on both resources
        parent_org = getattr(parent_resource, "organization_id", None)
        child_org = getattr(child_resource, "organization_id", None)

        if parent_org and child_org and cls.normalize_id(parent_org) != cls.normalize_id(child_org):
            raise TenantIsolationViolationError(
                f"Nested resource cross-tenant mismatch: {parent_type} tenant does not match {child_type} tenant."
            )

        # 2. Assert direct parent-child foreign key binding
        parent_id = cls.normalize_id(getattr(parent_resource, "id", None))
        child_parent_ref = cls.normalize_id(getattr(child_resource, parent_id_attr, None))

        if not parent_id or not child_parent_ref or parent_id != child_parent_ref:
            raise IDORViolationError(
                f"Nested resource IDOR violation: {child_type} does not belong to {parent_type}."
            )

    @classmethod
    def assert_resource_ownership(
        cls,
        user_id: str | UUID | None,
        resource_owner_id: str | UUID | None,
        resource_type: str = "resource",
        resource_id: str | UUID | None = None,
    ) -> None:
        """Assert that the user owns the specific resource when individual ownership is required."""
        u_id = cls.normalize_id(user_id)
        owner_id = cls.normalize_id(resource_owner_id)

        if not u_id or not owner_id or u_id != owner_id:
            res_id_str = f" id='{resource_id}'" if resource_id else ""
            raise IDORViolationError(
                f"Ownership violation: User does not own {resource_type}{res_id_str}."
            )
