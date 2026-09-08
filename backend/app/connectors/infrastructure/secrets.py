"""SecretProvider abstraction ensuring credentials are encrypted at rest and redacted in telemetry."""

import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet

from app.connectors.domain.errors import SecretDecryptionError
from app.core.config import Settings, get_settings

# Sensitive configuration keys subject to encryption and redaction
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "api_key",
        "token",
        "access_token",
        "refresh_token",
        "private_key",
        "credential",
        "auth_token",
        "connection_string",
    }
)

ENCRYPTED_PREFIX = "enc:v1:"


class SecretProvider:
    """Provides symmetric encryption for connector secrets at rest and sanitization for logs/APIs."""

    def __init__(self, settings: Settings | None = None, secret_key: str | None = None) -> None:
        self.settings = settings or get_settings()
        # Derive deterministic 32-byte key from secret_key or JWT_SECRET_KEY
        if secret_key:
            secret_bytes = secret_key.encode("utf-8")
        else:
            secret_bytes = self.settings.JWT_SECRET_KEY.encode("utf-8")
        key_hash = hashlib.sha256(secret_bytes).digest()
        fernet_key = base64.urlsafe_b64encode(key_hash)
        self._cipher = Fernet(fernet_key)

    def encrypt_value(self, plain_text: str) -> str:
        """Encrypt a single plaintext secret string."""
        if not plain_text or plain_text.startswith(ENCRYPTED_PREFIX):
            return plain_text
        token = self._cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")
        return f"{ENCRYPTED_PREFIX}{token}"

    def decrypt_value(self, cipher_token: str) -> str:
        """Decrypt an encrypted token string."""
        if not cipher_token or not cipher_token.startswith(ENCRYPTED_PREFIX):
            return cipher_token
        raw_token = cipher_token[len(ENCRYPTED_PREFIX) :]
        try:
            decrypted = self._cipher.decrypt(raw_token.encode("utf-8")).decode("utf-8")
            return decrypted
        except Exception as exc:
            raise SecretDecryptionError(f"Could not decrypt stored secret: {exc}") from exc

    def encrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Deeply scan configuration dict and encrypt any sensitive values."""
        encrypted: dict[str, Any] = {}
        for key, value in config.items():
            k_lower = key.lower()
            if isinstance(value, dict):
                encrypted[key] = self.encrypt_config(value)
            elif isinstance(value, str) and (
                k_lower in SENSITIVE_KEYS
                or any(s in k_lower for s in ("password", "secret", "api_key", "token"))
            ):
                encrypted[key] = self.encrypt_value(value)
            else:
                encrypted[key] = value
        return encrypted

    def decrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Deeply scan configuration dict and decrypt any encrypted tokens for runtime execution."""
        decrypted: dict[str, Any] = {}
        for key, value in config.items():
            if isinstance(value, dict):
                decrypted[key] = self.decrypt_config(value)
            elif isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX):
                decrypted[key] = self.decrypt_value(value)
            else:
                decrypted[key] = value
        return decrypted

    def redact_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return safe copy of configuration with sensitive values scrubbed for API responses/logs."""
        redacted: dict[str, Any] = {}
        for key, value in config.items():
            k_lower = key.lower()
            if isinstance(value, dict):
                redacted[key] = self.redact_config(value)
            elif (
                k_lower in SENSITIVE_KEYS
                or any(s in k_lower for s in ("password", "secret", "api_key", "token"))
                or isinstance(value, str)
                and value.startswith(ENCRYPTED_PREFIX)
            ):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        return redacted


_global_secret_provider: SecretProvider | None = None


def get_secret_provider() -> SecretProvider:
    """Singleton accessor for SecretProvider."""
    global _global_secret_provider
    if _global_secret_provider is None:
        _global_secret_provider = SecretProvider()
    return _global_secret_provider
