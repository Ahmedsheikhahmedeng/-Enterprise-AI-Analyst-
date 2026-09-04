"""API routes demonstrating and verifying RBAC authorization enforcement."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.postgres import get_db_session
from app.models.user import User
from app.rbac.catalog import (
    PERM_DOCUMENTS_READ,
    PERM_ORGANIZATION_READ,
    PERM_REPORTS_CREATE,
    PERM_USERS_MANAGE,
)
from app.rbac.dependencies import require_permission, resolve_organization_context
from app.rbac.schemas import (
    AssignRoleRequest,
    RBACActionResponse,
    RemoveRoleRequest,
    RoleResponse,
    UserEffectivePermissionsResponse,
)
from app.rbac.service import RBACService

rbac_router = APIRouter(prefix="/rbac", tags=["rbac"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])
_rbac_service = RBACService()


# ---------------------------------------------------------------------------
# Admin Demonstration Endpoints
# ---------------------------------------------------------------------------


@admin_router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    summary="Admin User Management Access",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid authentication token"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden - missing users.manage permission"},
    },
)
async def admin_get_users(
    current_user: Annotated[User, Depends(require_permission(PERM_USERS_MANAGE))],
) -> dict[str, Any]:
    """Demonstration admin endpoint requiring users.manage permission."""
    return {
        "message": "Admin user management access granted.",
        "user_id": str(current_user.id),
    }


# ---------------------------------------------------------------------------
# RBAC Demonstration Endpoints
# ---------------------------------------------------------------------------


@rbac_router.get(
    "/test/read-document",
    status_code=status.HTTP_200_OK,
    summary="Test Document Read Access",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid authentication token"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden - missing documents.read permission"},
    },
)
async def rbac_test_read_document(
    current_user: Annotated[User, Depends(require_permission(PERM_DOCUMENTS_READ))],
) -> dict[str, Any]:
    """Test endpoint requiring documents.read permission."""
    return {
        "message": "Document read access granted.",
        "user_id": str(current_user.id),
    }


@rbac_router.post(
    "/test/create-report",
    status_code=status.HTTP_200_OK,
    summary="Test Report Create Access",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid authentication token"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden - missing reports.create permission"},
    },
)
async def rbac_test_create_report(
    current_user: Annotated[User, Depends(require_permission(PERM_REPORTS_CREATE))],
) -> dict[str, Any]:
    """Test endpoint requiring reports.create permission."""
    return {
        "message": "Report create access granted.",
        "user_id": str(current_user.id),
    }


@rbac_router.get(
    "/permissions",
    response_model=UserEffectivePermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="List Effective Permissions for Active Organization Context",
)
async def get_my_effective_permissions(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    organization_id: Annotated[uuid.UUID, Depends(resolve_organization_context)],
) -> UserEffectivePermissionsResponse:
    """Return effective permissions and role for the user in the resolved organization."""
    permissions = await _rbac_service.get_effective_permissions(
        session=session,
        user_id=current_user.id,
        organization_id=organization_id,
    )
    role = await _rbac_service.get_user_role_for_organization(
        session=session,
        user_id=current_user.id,
        organization_id=organization_id,
    )
    return UserEffectivePermissionsResponse(
        user_id=current_user.id,
        organization_id=organization_id,
        role_id=role.id if role else None,
        role_name=role.name if role else None,
        permissions=sorted(permissions),
    )


@rbac_router.get(
    "/roles",
    response_model=list[RoleResponse],
    status_code=status.HTTP_200_OK,
    summary="List Available Roles",
)
async def list_available_roles(
    _: Annotated[User, Depends(require_permission(PERM_ORGANIZATION_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    organization_id: Annotated[uuid.UUID, Depends(resolve_organization_context)],
) -> list[RoleResponse]:
    """List system and organization roles available within the active organization context."""
    roles = await _rbac_service.repository.list_roles(
        session=session, organization_id=organization_id
    )
    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            organization_id=role.organization_id,
            permissions=[p.name for p in role.permissions],
        )
        for role in roles
    ]


@rbac_router.post(
    "/roles/assign",
    response_model=RBACActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign Role to Organization Member",
)
async def assign_user_role(
    payload: AssignRoleRequest,
    _: Annotated[User, Depends(require_permission(PERM_USERS_MANAGE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    resolved_org_id: Annotated[uuid.UUID, Depends(resolve_organization_context)],
) -> RBACActionResponse:
    """Assign a role to a user within the active organization context (requires users.manage)."""
    target_org_id = payload.organization_id or resolved_org_id
    member = await _rbac_service.assign_role(
        session=session,
        user_id=payload.user_id,
        organization_id=target_org_id,
        role_id=payload.role_id,
    )
    await session.commit()
    return RBACActionResponse(
        message="Role assigned successfully.",
        user_id=member.user_id,
        organization_id=member.organization_id,
        role_id=member.role_id,
    )


@rbac_router.post(
    "/roles/remove",
    response_model=RBACActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove Role/Membership from Organization Member",
)
async def remove_user_role(
    payload: RemoveRoleRequest,
    _: Annotated[User, Depends(require_permission(PERM_USERS_MANAGE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    resolved_org_id: Annotated[uuid.UUID, Depends(resolve_organization_context)],
) -> RBACActionResponse:
    """Remove a member's role and membership from the active organization context."""
    target_org_id = payload.organization_id or resolved_org_id
    await _rbac_service.remove_role(
        session=session,
        user_id=payload.user_id,
        organization_id=target_org_id,
    )
    await session.commit()
    return RBACActionResponse(
        message="Role removed successfully.",
        user_id=payload.user_id,
        organization_id=target_org_id,
        role_id=None,
    )
