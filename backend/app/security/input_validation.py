"""Centralized input validation defending against path traversal, control chars, and payload bombs."""

import re
import uuid
from typing import Any

from app.security.config import SecurityConfig, get_security_config
from app.security.exceptions import SecurityPolicyViolationError

PATH_TRAVERSAL_PATTERN = re.compile(r"(?:\.\.[\\/]|[\\/]\.\.|^\.\.$|%2e%2e|%2f|%5c)", re.IGNORECASE)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class SecurityInputValidator:
    """Validates parameters, query inputs, and filenames against adversarial payload structures."""

    def __init__(self, config: SecurityConfig | None = None) -> None:
        self.config = config or get_security_config()

    def validate_query_text(self, query: str | None) -> str:
        """Validate natural language query text length and structure."""
        if not query or not query.strip():
            raise SecurityPolicyViolationError("Query text cannot be empty.")
        if len(query) > self.config.max_query_length_chars:
            raise SecurityPolicyViolationError(
                f"Query text exceeds maximum allowed length ({self.config.max_query_length_chars} characters)."
            )
        # Check for null bytes
        if "\x00" in query:
            raise SecurityPolicyViolationError("Null byte injection detected in query input.")
        return query.strip()

    def validate_text(self, text: str | None, field_name: str = "text") -> str:
        """Validate generic input text against null bytes, control characters, and length abuse."""
        if not text:
            return ""
        if "\x00" in text:
            raise SecurityPolicyViolationError(f"Null bytes are prohibited in {field_name}.")
        if CONTROL_CHAR_PATTERN.search(text):
            raise SecurityPolicyViolationError(
                f"Dangerous control characters detected in {field_name}."
            )
        return text

    def validate_safe_path_identifier(
        self, identifier: str | None, field_name: str = "identifier"
    ) -> str:
        """Ensure an identifier does not contain directory traversal or path manipulation sequences."""
        if not identifier:
            raise SecurityPolicyViolationError(f"{field_name} cannot be empty.")
        clean = identifier.strip()
        if "\x00" in clean:
            raise SecurityPolicyViolationError(f"Null byte detected in {field_name}.")
        if PATH_TRAVERSAL_PATTERN.search(clean):
            raise SecurityPolicyViolationError(
                f"Path traversal sequences detected in {field_name}."
            )
        return clean

    def validate_safe_identifier(
        self, identifier: str | None, field_name: str = "identifier"
    ) -> str:
        """Alias for validate_safe_path_identifier."""
        return self.validate_safe_path_identifier(identifier, field_name)

    def validate_uuid(self, val: Any, field_name: str = "id") -> uuid.UUID:
        """Strictly validate and return a valid UUID object."""
        if isinstance(val, uuid.UUID):
            return val
        try:
            return uuid.UUID(str(val).strip())
        except (ValueError, TypeError, AttributeError) as exc:
            raise SecurityPolicyViolationError(
                f"Invalid UUID format provided for {field_name}."
            ) from exc


# Global singleton
_global_input_validator: SecurityInputValidator | None = None


def get_input_validator() -> SecurityInputValidator:
    """Singleton getter for SecurityInputValidator."""
    global _global_input_validator
    if _global_input_validator is None:
        _global_input_validator = SecurityInputValidator()
    return _global_input_validator
