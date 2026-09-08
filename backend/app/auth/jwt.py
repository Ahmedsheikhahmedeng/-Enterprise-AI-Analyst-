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


def decode_access_token(
    token: str,
    expected_issuer: str | None = None,
    expected_audience: str | None = None,
    leeway_seconds: int = 10,
) -> dict[str, Any]:
    """Decode and validate a JWT access token, enforcing signature, expiration, leeway, and token type.

    Strictly rejects alg=none, algorithm mismatches, expired tokens, not-yet-valid tokens,
    and missing standard claims (sub, exp, iat, jti).
    Raises UnauthorizedAppException on any verification or claim failure.
    """
    settings = get_settings()

    # Enforce strict algorithm allowlist (never permit 'none')
    allowed_algorithms = [settings.JWT_ALGORITHM]
    if "none" in [alg.lower() for alg in allowed_algorithms]:
        allowed_algorithms = [alg for alg in allowed_algorithms if alg.lower() != "none"]

    options: dict[str, Any] = {
        "verify_signature": True,
        "require": ["sub", "exp", "iat", "jti"],
        "verify_exp": True,
        "verify_iat": True,
        "verify_nbf": True,
    }

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=allowed_algorithms,
            options=options,  # type: ignore[arg-type]
            issuer=expected_issuer,
            audience=expected_audience,
            leeway=leeway_seconds,
        )
    except jwt.ExpiredSignatureError as err:
        raise UnauthorizedAppException(
            message="Access token has expired.",
            code="TOKEN_EXPIRED",
        ) from err
    except jwt.ImmatureSignatureError as err:
        raise UnauthorizedAppException(
            message="Access token is not yet valid (nbf/iat in future).",
            code="TOKEN_NOT_YET_VALID",
        ) from err
    except jwt.InvalidAlgorithmError as err:
        raise UnauthorizedAppException(
            message="Token algorithm is not allowed or invalid.",
            code="INVALID_ALGORITHM",
        ) from err
    except jwt.InvalidIssuerError as err:
        raise UnauthorizedAppException(
            message="Token issuer verification failed.",
            code="INVALID_ISSUER",
        ) from err
    except jwt.InvalidAudienceError as err:
        raise UnauthorizedAppException(
            message="Token audience verification failed.",
            code="INVALID_AUDIENCE",
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
