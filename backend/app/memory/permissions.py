"""RBAC permission enforcement helpers for Enterprise Agent Memory."""

from app.memory.exceptions import MemoryAccessDeniedError
from app.rbac.catalog import (
    PERM_MEMORY_ADMIN,
)


def require_memory_permission(user_permissions: set[str], required_perm: str) -> None:
    """Ensure user has required permission or administrative override."""
    if PERM_MEMORY_ADMIN in user_permissions:
        return
    if required_perm not in user_permissions:
        from uuid import uuid4

        raise MemoryAccessDeniedError(
            uuid4(),
            f"User lacks required permission '{required_perm}'.",
        )
