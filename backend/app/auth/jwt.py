import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedAppException


def create_access_token(
    user_id: uuid.UUID,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed, short-lived JWT access token with standard RFC-compliant claims."""
    settings = get_settings()
    now = datetime.now(UTC)
    expiration = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token, enforcing signature, expiration, and token type.

    Raises UnauthorizedAppException on any verification or claim failure.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
    except jwt.ExpiredSignatureError as err:
        raise UnauthorizedAppException(
            message="Access token has expired.",
            code="TOKEN_EXPIRED",
        ) from err
    except jwt.PyJWTError as err:
        raise UnauthorizedAppException(
            message="Could not validate access token.",
            code="INVALID_TOKEN",
        ) from err

    token_type = payload.get("type")
    if token_type != "access":
        raise UnauthorizedAppException(
            message=f"Invalid token type '{token_type}'. Access token expected.",
            code="INVALID_TOKEN_TYPE",
        )

    return payload
