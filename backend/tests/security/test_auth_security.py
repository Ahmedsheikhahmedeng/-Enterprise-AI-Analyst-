"""Authentication Security Tests — TASK 22.

Verifies:
- alg=none JWT rejection
- Algorithm mismatch rejection
- Expired token rejection
- Not-yet-valid token rejection (nbf/iat in future)
- Signature tampering rejection
- Wrong token type rejection
- Clock skew leeway behavior
"""

import time
import uuid

import jwt
import pytest

from app.auth.jwt import create_access_token, decode_access_token
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedAppException


def test_valid_access_token_decodes_successfully() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload


def test_jwt_alg_none_rejected() -> None:
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + 3600,
        "jti": str(uuid.uuid4()),
    }
    # Forge token with alg=none without valid signature
    unsigned_token = jwt.encode(payload, key="", algorithm="none")

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(unsigned_token)
    assert exc_info.value.code in ("INVALID_ALGORITHM", "INVALID_TOKEN")


def test_jwt_algorithm_mismatch_rejected() -> None:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + 3600,
        "jti": str(uuid.uuid4()),
    }
    # Sign using HS512 while system expects HS256
    mismatched_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS512")

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(mismatched_token)
    assert exc_info.value.code in ("INVALID_ALGORITHM", "INVALID_TOKEN")


def test_jwt_expired_token_rejected() -> None:
    settings = get_settings()
    past = int(time.time()) - 100
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": past - 3600,
        "exp": past,
        "jti": str(uuid.uuid4()),
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(expired_token)
    assert exc_info.value.code == "TOKEN_EXPIRED"


def test_jwt_future_not_before_rejected() -> None:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "nbf": now + 1000,
        "exp": now + 3600,
        "jti": str(uuid.uuid4()),
    }
    future_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(future_token)
    assert exc_info.value.code == "TOKEN_NOT_YET_VALID"


def test_jwt_signature_tampering_rejected() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id)

    # Tamper with the signature bytes at the end
    parts = token.split(".")
    tampered_sig = parts[2][:-4] + "AAAA"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(tampered_token)
    assert exc_info.value.code == "INVALID_TOKEN"


def test_jwt_wrong_token_type_rejected() -> None:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "refresh",  # refresh token supplied where access expected
        "iat": now,
        "exp": now + 3600,
        "jti": str(uuid.uuid4()),
    }
    refresh_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(refresh_token)
    assert exc_info.value.code == "INVALID_TOKEN_TYPE"


def test_jwt_clock_skew_leeway_tolerates_minor_drift() -> None:
    settings = get_settings()
    now = int(time.time())
    # Token expired 5 seconds ago, leeway is 10 seconds -> should pass
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": now - 3600,
        "exp": now - 5,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    decoded = decode_access_token(token, leeway_seconds=10)
    assert decoded["sub"] == payload["sub"]
