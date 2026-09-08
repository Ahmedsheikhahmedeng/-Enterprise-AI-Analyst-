"""Centralized redaction layer ensuring zero secret, credential, or prompt leakage."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.observability.config import ObservabilityConfig, get_observability_config


class TelemetryRedactor:
    """Sanitizes strings, headers, dictionaries, and telemetry attributes against credential leakage."""

    REDACTED_STR = "[REDACTED]"

    # Pattern detecting Bearer tokens (JWT, OAuth)
    BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-_=.]+")

    # Pattern detecting OpenAI / Anthropic / general API keys
    API_KEY_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9]{16,}|ant-[A-Za-z0-9\-_]{16,})\b")

    # Pattern detecting connection string passwords in URIs (postgresql://user:password@host/db)
    DSN_PASSWORD_PATTERN = re.compile(r"(://[^:]+:)([^@/]+)(@)")

    # Pattern detecting private key blocks
    PRIVATE_KEY_PATTERN = re.compile(
        r"-----BEGIN\s+[A-Z0-9_\s]+PRIVATE\s+KEY-----.*?-----END\s+[A-Z0-9_\s]+PRIVATE\s+KEY-----",
        re.DOTALL,
    )

    def __init__(self, config: ObservabilityConfig | None = None) -> None:
        self.config = config or get_observability_config()
        self.sensitive_keys = set(self.config.sensitive_keys)

    def redact_text(self, text: str) -> str:
        """Redact known credential tokens, API keys, DSN credentials, and private keys from text."""
        if not text:
            return ""

        # 1. Redact Private Key blocks
        text = self.PRIVATE_KEY_PATTERN.sub(
            f"-----BEGIN PRIVATE KEY-----\n{self.REDACTED_STR}\n-----END PRIVATE KEY-----",
            text,
        )

        # 2. Redact DSN password
        text = self.DSN_PASSWORD_PATTERN.sub(rf"\g<1>{self.REDACTED_STR}\g<3>", text)

        # 3. Redact Bearer tokens
        text = self.BEARER_PATTERN.sub(f"Bearer {self.REDACTED_STR}", text)

        # 4. Redact API keys
        text = self.API_KEY_PATTERN.sub(self.REDACTED_STR, text)

        return text

    def redact_data(self, data: Any) -> Any:
        """Recursively redact sensitive keys and values across dicts, lists, and primitives."""
        if isinstance(data, str):
            return self.redact_text(data)

        if isinstance(data, Mapping):
            redacted_dict: dict[str, Any] = {}
            for k, v in data.items():
                str_k = str(k).lower()
                # If key name itself indicates sensitive credential
                if any(sens in str_k for sens in self.sensitive_keys):
                    redacted_dict[k] = self.REDACTED_STR
                else:
                    redacted_dict[k] = self.redact_data(v)
            return redacted_dict

        if isinstance(data, Sequence) and not isinstance(data, (bytes, bytearray)):
            return [self.redact_data(item) for item in data]

        return data
