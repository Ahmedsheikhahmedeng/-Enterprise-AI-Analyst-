"""FastAPI dependencies for tenant context resolution and tenant permission enforcement."""

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.core.exceptions import ForbiddenAppException, ValidationAppException
from app.core.logging import get_logger
from app.db.postgres import get_db_session
from app.models.organization import Organization
from app.models.role import OrganizationMember
from app.models.user import User
from app.rbac.repository import RBACRepository
from app.tenancy.context import TenantContext

logger = get_logger("tenancy.dependencies")
_rbac_repo = RBACRepository()


async def get_current_tenant(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    x_organization_id: Annotated[str | None, Header(alias="X-Organization-ID")] = None,
    organization_id_query: Annotated[uuid.UUID | None, Query(alias="organization_id")] = None,
) -> TenantContext:
    """Resolve and validate the active TenantContext for the authenticated caller.

    Resolution Pipeline:
    1. Parse and sanitize X-Organization-ID (or query parameter).
    2. Fallback to single membership if caller belongs to exactly one organization.
    3. Reject ambiguous (>1 memberships without header) or missing memberships.
    4. Validate that the target organization exists and is active.
    5. Validate caller's membership in the target organization.
    6. Verify that caller's assigned role is valid and tenant-scoped.
    7. Load effective permissions in a single joined query.
    8. Emit structured security audit event and return immutable TenantContext.
    """
    target_org_id: uuid.UUID

    if x_organization_id is not None:
        try:
            target_org_id = uuid.UUID(x_organization_id)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Invalid X-Organization-ID header provided",
                audit_event="tenant_membership_denied",
                user_id=str(current_user.id),
                raw_header=x_organization_id,
            )
            raise ValidationAppException(
                message="The provided X-Organization-ID is not a valid UUID.",
                code="INVALID_ORGANIZATION_ID",
            ) from exc
    elif organization_id_query is not None:
        target_org_id = organization_id_query
    else:
        memberships = await _rbac_repo.list_user_memberships(session, current_user.id)
        if len(memberships) == 1:
            target_org_id = memberships[0].organization_id
        elif len(memberships) == 0:
            logger.warning(
                "User has no organization memberships",
                audit_event="tenant_membership_denied",
                user_id=str(current_user.id),
            )
            raise ForbiddenAppException(
                message="You do not have permission to perform this action.",
                code="FORBIDDEN",
            )
        else:
            logger.warning(
                "Ambiguous organization context for multi-tenant user",
                audit_event="tenant_membership_denied",
                user_id=str(current_user.id),
                membership_count=len(memberships),
            )
            raise ForbiddenAppException(
                message="Organization context must be specified via X-Organization-ID header.",
                code="AMBIGUOUS_TENANT_CONTEXT",
            )

    # Validate Organization status
    org_stmt = select(Organization).where(Organization.id == target_org_id)
    org_result = await session.execute(org_stmt)
    org = org_result.scalar_one_or_none()

    if org is None:
        logger.warning(
            "Target organization does not exist",
            audit_event="tenant_membership_denied",
            user_id=str(current_user.id),
            target_organization_id=str(target_org_id),
        )
        raise ForbiddenAppException(
            message="You do not have permission to perform this action.",
            code="FORBIDDEN",
        )

    if not org.is_active:
        logger.warning(
            "Target organization is deactivated",
            audit_event="tenant_membership_denied",
            user_id=str(current_user.id),
            target_organization_id=str(target_org_id),
        )
        raise ForbiddenAppException(
            message="Organization is inactive or disabled.",
            code="ORGANIZATION_INACTIVE",
        )

    # Validate Membership and Role
    member_stmt = (
        select(OrganizationMember)
        .where(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.organization_id == target_org_id,
        )
        .options(selectinload(OrganizationMember.role))
    )
    member_result = await session.execute(member_stmt)
    member = member_result.scalar_one_or_none()

    if member is None:
        logger.warning(
            "Cross-tenant access attempt: User is not a member of organization",
            audit_event="cross_tenant_access_denied",
            user_id=str(current_user.id),
            target_organization_id=str(target_org_id),
        )
        raise ForbiddenAppException(
            message="You do not have permission to perform this action.",
            code="FORBIDDEN",
        )

    # Cross-tenant role check (role must belong to target org or be system-wide)
    if member.role.organization_id is not None and member.role.organization_id != target_org_id:
        logger.warning(
            "Cross-tenant role mismatch detected for organization member",
            audit_event="cross_tenant_access_denied",
            user_id=str(current_user.id),
            target_organization_id=str(target_org_id),
            role_organization_id=str(member.role.organization_id),
        )
        raise ForbiddenAppException(
            message="You do not have permission to perform this action.",
            code="FORBIDDEN",
        )

    # Load effective permissions in single query
    permissions = await _rbac_repo.get_effective_user_permissions(
        session=session,
        user_id=current_user.id,
        organization_id=target_org_id,
    )

    logger.info(
        "Tenant context successfully resolved",
        audit_event="tenant_context_resolved",
        user_id=str(current_user.id),
        organization_id=str(target_org_id),
        role_name=member.role.name,
    )

    return TenantContext(
        organization_id=target_org_id,
        user_id=current_user.id,
        membership_id=member.id,
        role_id=member.role_id,
        role_name=member.role.name,
        permissions=frozenset(permissions),
    )


# Backward-compatible alias for tenant context dependency
get_tenant_context = get_current_tenant


def require_tenant_permission(
    permission_name: str,
) -> Callable[..., Coroutine[Any, Any, TenantContext]]:
    """Create a reusable FastAPI dependency requiring a valid tenant context and permission."""

    async def _permission_dependency(
        tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    ) -> TenantContext:
        if not tenant.has_permission(permission_name):
            logger.warning(
                "Access authorization denied for tenant member",
                audit_event="authorization_denied",
                user_id=str(tenant.user_id),
                organization_id=str(tenant.organization_id),
                permission=permission_name,
            )
            raise ForbiddenAppException(
                message="You do not have permission to perform this action.",
                code="FORBIDDEN",
            )
        return tenant

    return _permission_dependency
