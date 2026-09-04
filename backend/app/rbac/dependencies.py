"""FastAPI authorization dependencies for RBAC and permission enforcement."""

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import ForbiddenAppException
from app.db.postgres import get_db_session
from app.models.user import User
from app.rbac.repository import RBACRepository
from app.rbac.service import RBACService

_rbac_repo = RBACRepository()
_rbac_service = RBACService(repository=_rbac_repo)


async def resolve_organization_context(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    x_organization_id: Annotated[str | None, Header(alias="X-Organization-ID")] = None,
    organization_id_query: Annotated[uuid.UUID | None, Query(alias="organization_id")] = None,
) -> uuid.UUID:
    """Resolve the active organization context for the authenticated user.

    Order of resolution:
    1. Explicit X-Organization-ID request header
    2. Explicit organization_id query parameter
    3. User's single organization membership if exactly one exists

    If ambiguous (>1 memberships without header) or nonexistent (0 memberships),
    raises 403 Forbidden with standard error contract.
    """
    if x_organization_id is not None:
        try:
            return uuid.UUID(x_organization_id)
        except (ValueError, TypeError) as exc:
            _rbac_service.log_authorization_denied(
                user_id=current_user.id,
                organization_id=None,
                permission="context.resolve",
            )
            raise ForbiddenAppException(
                message="You do not have permission to perform this action.",
                code="FORBIDDEN",
            ) from exc

    if organization_id_query is not None:
        return organization_id_query

    # Fallback to single organization membership resolution
    memberships = await _rbac_repo.list_user_memberships(session, current_user.id)
    if len(memberships) == 1:
        return memberships[0].organization_id

    _rbac_service.log_authorization_denied(
        user_id=current_user.id,
        organization_id=None,
        permission="context.ambiguous_or_missing",
    )
    raise ForbiddenAppException(
        message="You do not have permission to perform this action.",
        code="FORBIDDEN",
    )


def require_permission(
    permission_name: str,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """Create a reusable FastAPI dependency enforcing a permission in the org context.

    Authenticates user via get_current_user (emitting 401 if missing/invalid/expired),
    resolves the active organization context, and verifies permissions (emitting 403 if forbidden).
    """

    async def _permission_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db_session)],
        organization_id: Annotated[uuid.UUID, Depends(resolve_organization_context)],
    ) -> User:
        has_perm = await _rbac_service.has_permission(
            session=session,
            user_id=current_user.id,
            organization_id=organization_id,
            permission_name=permission_name,
        )

        if not has_perm:
            _rbac_service.log_authorization_denied(
                user_id=current_user.id,
                organization_id=organization_id,
                permission=permission_name,
            )
            raise ForbiddenAppException(
                message="You do not have permission to perform this action.",
                code="FORBIDDEN",
            )

        return current_user

    return _permission_dependency
