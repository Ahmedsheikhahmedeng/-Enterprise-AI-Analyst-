from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.exceptions import ValidationAppException

# Argon2id password hasher with secure defaults
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def validate_password_policy(password: str) -> None:
    """Validate that the password satisfies baseline complexity and length requirements."""
    if not password or len(password) < 8:
        raise ValidationAppException(
            message="Password must be at least 8 characters in length.",
            code="WEAK_PASSWORD",
            details={"min_length": 8},
        )


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Plaintext passwords must never be persisted or logged.
    """
    validate_password_policy(password)
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash in constant time."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False
