"""Secret redaction and safe logging utilities preventing credential leakage."""

from typing import Any

from app.core.logging import get_logger
from app.observability.redaction import TelemetryRedactor

logger = get_logger("security.secrets")


class SecretSafeLogger:
    """Wraps telemetry redaction to safely sanitize log messages and payloads before output."""

    def __init__(self, redactor: TelemetryRedactor | None = None) -> None:
        self.redactor = redactor or TelemetryRedactor()

    def redact_text(self, text: str) -> str:
        """Sanitize raw text string from tokens, DSN passwords, and keys."""
        return self.redactor.redact_text(text)

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize sensitive key-value pairs."""
        redacted = self.redactor.redact_data(data)
        return redacted if isinstance(redacted, dict) else dict(data)

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Classmethod helper to sanitize raw text."""
        return get_secret_safe_logger().redact_text(text)

    @classmethod
    def sanitize_mapping(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Classmethod helper to sanitize mappings."""
        return get_secret_safe_logger().redact_dict(data)

    def log_safe_info(self, message: str, **kwargs: Any) -> None:
        """Emit sanitized INFO level structured log."""
        clean_msg = self.redact_text(message)
        clean_kwargs = self.redactor.redact_data(kwargs)
        logger.info(clean_msg, **clean_kwargs)

    def log_safe_warning(self, message: str, **kwargs: Any) -> None:
        """Emit sanitized WARNING level structured log."""
        clean_msg = self.redact_text(message)
        clean_kwargs = self.redactor.redact_data(kwargs)
        logger.warning(clean_msg, **clean_kwargs)

    def log_safe_error(self, message: str, **kwargs: Any) -> None:
        """Emit sanitized ERROR level structured log."""
        clean_msg = self.redact_text(message)
        clean_kwargs = self.redactor.redact_data(kwargs)
        logger.error(clean_msg, **clean_kwargs)


# Global singleton
_global_secret_safe_logger: SecretSafeLogger | None = None


def get_secret_safe_logger() -> SecretSafeLogger:
    """Singleton getter for SecretSafeLogger."""
    global _global_secret_safe_logger
    if _global_secret_safe_logger is None:
        _global_secret_safe_logger = SecretSafeLogger()
    return _global_secret_safe_logger
