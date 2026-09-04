"""RBAC business service layer orchestrating permission evaluation and role management."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppException
from app.core.logging import get_logger
from app.models.role import OrganizationMember, Role
from app.rbac.catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    SYSTEM_PERMISSIONS,
    SYSTEM_ROLES,
)
from app.rbac.repository import RBACRepository

logger = get_logger("rbac.service")


class RBACService:
    """Service providing authorization evaluation, role assignments, and catalog seeding."""

    def __init__(self, repository: RBACRepository | None = None) -> None:
        self.repository = repository or RBACRepository()

    async def has_permission(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        permission_name: str,
    ) -> bool:
        """Check if an authenticated user possesses a specific permission in an organization."""
        effective_permissions = await self.get_effective_permissions(
            session=session,
            user_id=user_id,
            organization_id=organization_id,
        )
        return permission_name in effective_permissions

    async def get_effective_permissions(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> set[str]:
        """Retrieve all active, scoped permission names for a user in an organization."""
        return await self.repository.get_effective_user_permissions(
            session=session,
            user_id=user_id,
            organization_id=organization_id,
        )

    async def get_user_role_for_organization(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Role | None:
        """Retrieve the assigned Role entity for a user within an organization context."""
        member = await self.repository.get_organization_member(
            session=session,
            user_id=user_id,
            organization_id=organization_id,
        )
        return member.role if member else None

    async def assign_role(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> OrganizationMember:
        """Assign or update a role for an organization member with audit logging."""
        try:
            member = await self.repository.assign_role_to_member(
                session=session,
                user_id=user_id,
                organization_id=organization_id,
                role_id=role_id,
            )
        except ValueError as exc:
            raise ValidationAppException(
                message=str(exc),
                code="INVALID_ROLE_ASSIGNMENT",
            ) from exc

        logger.info(
            "Role successfully assigned to organization member",
            audit_event="role_assigned",
            user_id=str(user_id),
            organization_id=str(organization_id),
            role_id=str(role_id),
        )
        return member

    async def remove_role(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> bool:
        """Remove a member's role and membership from an organization with audit logging."""
        removed = await self.repository.remove_role_from_member(
            session=session,
            user_id=user_id,
            organization_id=organization_id,
        )
        if removed:
            logger.info(
                "Role removed from organization member",
                audit_event="role_removed",
                user_id=str(user_id),
                organization_id=str(organization_id),
            )
        return removed

    def log_authorization_denied(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID | None,
        permission: str,
        resource: str | None = None,
        action: str | None = None,
    ) -> None:
        """Log structured audit event when an authorization check fails."""
        logger.warning(
            "Access authorization denied for user",
            audit_event="authorization_denied",
            user_id=str(user_id),
            organization_id=str(organization_id) if organization_id else None,
            permission=permission,
            resource=resource or permission.split(".")[0],
            action=action or permission.split(".")[1] if "." in permission else None,
        )

    async def seed_system_rbac(self, session: AsyncSession) -> tuple[int, int, int]:
        """Idempotently seed the system catalog with permissions, system roles, and mappings.

        Returns (permissions_seeded, roles_seeded, role_permissions_seeded).
        """
        # 1. Seed Permissions
        perm_entities: dict[str, uuid.UUID] = {}
        perms_seeded = 0
        for name, desc in SYSTEM_PERMISSIONS.items():
            existing = await self.repository.get_permission_by_name(session, name)
            if existing is None:
                new_perm = await self.repository.create_permission(
                    session, name=name, description=desc
                )
                perm_entities[name] = new_perm.id
                perms_seeded += 1
            else:
                perm_entities[name] = existing.id

        # 2. Seed System Roles (organization_id=None)
        role_entities: dict[str, uuid.UUID] = {}
        roles_seeded = 0
        for name, desc in SYSTEM_ROLES.items():
            existing_role = await self.repository.get_role_by_name(
                session, name=name, organization_id=None
            )
            if existing_role is None:
                new_role = await self.repository.create_role(
                    session, name=name, description=desc, organization_id=None
                )
                role_entities[name] = new_role.id
                roles_seeded += 1
            else:
                role_entities[name] = existing_role.id

        # 3. Seed Role-to-Permission Mappings
        mappings_seeded = 0
        for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
            role_id = role_entities[role_name]
            for perm_name in perm_names:
                perm_id = perm_entities[perm_name]
                await self.repository.assign_permission_to_role(
                    session, role_id=role_id, permission_id=perm_id
                )
                mappings_seeded += 1

        await session.flush()
        return perms_seeded, roles_seeded, mappings_seeded
