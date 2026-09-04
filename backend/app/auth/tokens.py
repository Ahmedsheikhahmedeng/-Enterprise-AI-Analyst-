import hashlib
import secrets


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure, high-entropy URL-safe random token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """Compute the SHA-256 digest of a high-entropy security token for safe database storage.

    Raw tokens are never persisted to disk or logged.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
