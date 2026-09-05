"""TenantContext model representing the verified active tenant execution scope."""

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Request-scoped immutable context encapsulating tenant identity and permissions.

    A valid TenantContext guarantees that:
    1. The user has been authenticated.
    2. The organization exists and is active.
    3. The user holds a valid, active membership within the organization.
    4. The user's role belongs to the organization (or is a system-wide role).
    5. The effective permissions represent the exact privileges granted within this organization.
    """

    organization_id: uuid.UUID
    user_id: uuid.UUID
    membership_id: uuid.UUID
    role_id: uuid.UUID
    role_name: str
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has_permission(self, permission: str) -> bool:
        """Check whether the context possesses a specific granular permission."""
        return permission in self.permissions

    def has_any_permission(self, *permissions: str) -> bool:
        """Check whether the context possesses at least one of the specified permissions."""
        return any(perm in self.permissions for perm in permissions)

    def has_all_permissions(self, *permissions: str) -> bool:
        """Check whether the context possesses all of the specified permissions."""
        return all(perm in self.permissions for perm in permissions)
