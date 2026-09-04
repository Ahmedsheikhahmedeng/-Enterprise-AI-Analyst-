"""Asynchronous SQLAlchemy repository for RBAC roles, permissions, and memberships."""

import uuid
from collections.abc import Sequence

from sqlalchemy import CursorResult, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import OrganizationMember, Permission, Role, RolePermission


class RBACRepository:
    """Repository handling all database queries for permissions, roles, and member mappings."""

    async def get_permission_by_name(self, session: AsyncSession, name: str) -> Permission | None:
        """Find a permission by its unique name."""
        stmt = select(Permission).where(Permission.name == name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_permissions(self, session: AsyncSession) -> Sequence[Permission]:
        """List all system permissions in the catalog."""
        stmt = select(Permission).order_by(Permission.name.asc())
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_permission(
        self, session: AsyncSession, name: str, description: str | None = None
    ) -> Permission:
        """Create and persist a new permission entity."""
        permission = Permission(name=name, description=description)
        session.add(permission)
        await session.flush()
        return permission

    async def get_role_by_id(self, session: AsyncSession, role_id: uuid.UUID) -> Role | None:
        """Find a role by ID with permissions eagerly loaded."""
        stmt = select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_role_by_name(
        self,
        session: AsyncSession,
        name: str,
        organization_id: uuid.UUID | None = None,
    ) -> Role | None:
        """Find a role by name within an organization or system-wide (organization_id=None)."""
        if organization_id is None:
            stmt = (
                select(Role)
                .where(Role.name == name, Role.organization_id.is_(None))
                .options(selectinload(Role.permissions))
            )
        else:
            stmt = (
                select(Role)
                .where(Role.name == name, Role.organization_id == organization_id)
                .options(selectinload(Role.permissions))
            )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_roles(
        self, session: AsyncSession, organization_id: uuid.UUID | None = None
    ) -> Sequence[Role]:
        """List all system roles and optionally organization-scoped roles."""
        if organization_id is None:
            stmt = (
                select(Role)
                .where(Role.organization_id.is_(None))
                .options(selectinload(Role.permissions))
                .order_by(Role.name.asc())
            )
        else:
            stmt = (
                select(Role)
                .where(
                    or_(
                        Role.organization_id.is_(None),
                        Role.organization_id == organization_id,
                    )
                )
                .options(selectinload(Role.permissions))
                .order_by(Role.name.asc())
            )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_role(
        self,
        session: AsyncSession,
        name: str,
        description: str | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> Role:
        """Create a new role entity."""
        role = Role(
            name=name,
            description=description,
            organization_id=organization_id,
        )
        session.add(role)
        await session.flush()
        return role

    async def assign_permission_to_role(
        self, session: AsyncSession, role_id: uuid.UUID, permission_id: uuid.UUID
    ) -> RolePermission:
        """Associate a permission to a role in role_permissions table."""
        stmt = select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        assoc = RolePermission(role_id=role_id, permission_id=permission_id)
        session.add(assoc)
        await session.flush()
        return assoc

    async def remove_permission_from_role(
        self, session: AsyncSession, role_id: uuid.UUID, permission_id: uuid.UUID
    ) -> bool:
        """Remove a permission association from a role."""
        stmt = delete(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
        result = await session.execute(stmt)
        return bool(result.rowcount > 0) if isinstance(result, CursorResult) else True

    async def get_organization_member(
        self, session: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> OrganizationMember | None:
        """Look up user membership in an organization with role eagerly loaded."""
        stmt = (
            select(OrganizationMember)
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id,
            )
            .options(selectinload(OrganizationMember.role).selectinload(Role.permissions))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_user_memberships(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> Sequence[OrganizationMember]:
        """List all organization memberships for a user."""
        stmt = (
            select(OrganizationMember)
            .where(OrganizationMember.user_id == user_id)
            .options(selectinload(OrganizationMember.role))
            .order_by(OrganizationMember.created_at.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_effective_user_permissions(
        self, session: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> set[str]:
        """Fetch all effective permission names for a user within an organization in a single query.

        Strictly prevents N+1 queries. Respects role ownership: if a role is scoped to
        another organization, it will not grant any permissions in this organization context.
        """
        stmt = (
            select(Permission.name)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(Role, RolePermission.role_id == Role.id)
            .join(OrganizationMember, OrganizationMember.role_id == Role.id)
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id,
                or_(
                    Role.organization_id.is_(None),
                    Role.organization_id == organization_id,
                ),
            )
        )
        result = await session.execute(stmt)
        return set(result.scalars().all())

    async def assign_role_to_member(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> OrganizationMember:
        """Assign or update a role for an organization member.

        Validates that the role belongs to the organization or is system-wide.
        """
        # Validate role existence and tenant scoping
        role_stmt = select(Role).where(Role.id == role_id)
        role_res = await session.execute(role_stmt)
        role = role_res.scalar_one_or_none()
        if role is None:
            raise ValueError(f"Role {role_id} does not exist.")

        if role.organization_id is not None and role.organization_id != organization_id:
            raise ValueError(
                f"Role {role_id} belongs to organization {role.organization_id} "
                f"and cannot be assigned within organization {organization_id}."
            )

        # Check existing membership
        member_stmt = select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        )
        member_res = await session.execute(member_stmt)
        member = member_res.scalar_one_or_none()

        if member is not None:
            member.role_id = role_id
            await session.flush()
            return member

        # Create new membership
        new_member = OrganizationMember(
            user_id=user_id,
            organization_id=organization_id,
            role_id=role_id,
        )
        session.add(new_member)
        await session.flush()
        return new_member

    async def remove_role_from_member(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> bool:
        """Remove an organization member's role and membership."""
        stmt = delete(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        )
        result = await session.execute(stmt)
        return bool(result.rowcount > 0) if isinstance(result, CursorResult) else True
