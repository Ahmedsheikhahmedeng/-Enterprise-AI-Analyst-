import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.auth.repository import AuthRepository
from app.core.exceptions import UnauthorizedAppException
from app.db.postgres import get_db_session
from app.models.user import User

# Standard bearer scheme; auto_error=False allows emitting structured JSON error envelopes
_bearer_scheme = HTTPBearer(auto_error=False)
_auth_repo = AuthRepository()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Extract and validate JWT access token from request header and return the authenticated User.

    Emits consistent 401 Unauthorized errors conforming to the standardized error schema.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedAppException(
            message="Authentication credentials were not provided or scheme is invalid.",
            code="MISSING_CREDENTIALS",
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedAppException(
            message="Invalid access token subject.",
            code="INVALID_TOKEN",
        )

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError) as err:
        raise UnauthorizedAppException(
            message="Access token subject is not a valid UUID.",
            code="INVALID_TOKEN",
        ) from err

    user = await _auth_repo.get_user_by_id(session, user_id)
    if user is None:
        raise UnauthorizedAppException(
            message="Authenticated user account no longer exists.",
            code="USER_NOT_FOUND",
        )

    if not user.is_active:
        raise UnauthorizedAppException(
            message="Authenticated user account is inactive or disabled.",
            code="INACTIVE_USER",
        )

    return user
