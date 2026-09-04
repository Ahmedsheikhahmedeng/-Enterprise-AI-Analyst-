import uuid
from datetime import timedelta

import jwt
import pytest

from app.auth.jwt import create_access_token, decode_access_token
from app.auth.password import hash_password, validate_password_policy, verify_password
from app.auth.tokens import generate_secure_token, hash_token
from app.core.exceptions import UnauthorizedAppException, ValidationAppException


def test_password_hashing_and_verification() -> None:
    """Verify Argon2id password hashing and constant-time verification."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    # Argon2id prefix check
    assert hashed.startswith("$argon2id$")
    # Verify plain password matches
    assert verify_password(password, hashed) is True
    # Verify mismatch
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "") is False


def test_password_policy_enforcement() -> None:
    """Verify minimum 8-character password policy."""
    with pytest.raises(ValidationAppException) as exc_info:
        validate_password_policy("short")
    assert exc_info.value.code == "WEAK_PASSWORD"

    # 8 characters passes
    validate_password_policy("12345678")


def test_token_generation_and_hashing() -> None:
    """Verify high-entropy random token generation and SHA-256 digests."""
    t1 = generate_secure_token()
    t2 = generate_secure_token()
    assert t1 != t2
    assert len(t1) >= 32

    h1 = hash_token(t1)
    h2 = hash_token(t2)
    assert len(h1) == 64
    assert len(h2) == 64
    assert h1 != h2
    # Deterministic hashing
    assert hash_token(t1) == h1


def test_jwt_access_token_claims_and_decoding() -> None:
    """Verify access token creation contains required RFC claims."""
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload
    assert payload["exp"] > payload["iat"]


def test_jwt_access_token_expired_raises_unauthorized() -> None:
    """Verify expired JWT access token is rejected with TOKEN_EXPIRED."""
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, expires_delta=timedelta(seconds=-10))

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.code == "TOKEN_EXPIRED"


def test_jwt_invalid_token_type_rejected() -> None:
    """Verify tokens with type != 'access' are rejected."""
    # Craft a JWT with type='refresh'
    from app.core.config import get_settings

    settings = get_settings()
    user_id = uuid.uuid4()
    bad_payload = {
        "sub": str(user_id),
        "type": "refresh",  # Not access
        "iat": 100000,
        "exp": 9999999999,
        "jti": str(uuid.uuid4()),
    }
    bad_token = jwt.encode(bad_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(bad_token)
    assert exc_info.value.code == "INVALID_TOKEN_TYPE"


def test_jwt_invalid_signature_rejected() -> None:
    """Verify tokens signed with foreign secrets are rejected."""
    user_id = uuid.uuid4()
    tampered_token = jwt.encode(
        {"sub": str(user_id), "type": "access", "iat": 10000, "exp": 9999999999, "jti": "abc"},
        "wrong-secret-key-12345678901234567890",
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedAppException) as exc_info:
        decode_access_token(tampered_token)
    assert exc_info.value.code == "INVALID_TOKEN"
