"""Privacy and access policies governing Enterprise Agent Memory."""

import re
import uuid
from typing import Any

from app.memory.exceptions import (
    MemoryAccessDeniedError,
    MemoryPrivacyViolationError,
)
from app.memory.schemas import MemoryPrivacyLevel, MemoryStatus, MemoryVisibility

# Regex patterns for sensitive secret detection
SECRET_PATTERNS = [
    (r"ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*", "jwt_token"),
    (r"(?:Bearer\s+[A-Za-z0-9\-._~+/]+=*)", "bearer_token"),
    (r"(?:(?:sk|pk|api)_(?:live|test|prod)_[0-9a-zA-Z]{20,})", "api_key"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "private_key"),
    (r"(?:postgres|mysql|mongodb|redis):\/\/[^\s]+", "connection_string"),
    (
        r"(?:password|passwd|secret|api_key|access_token)\s*[:=]\s*['\"][^'\"]+['\"]",
        "credential_assignment",
    ),
    (r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "credit_card"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "ssn"),
]


class MemoryPrivacyFilter:
    """Detects and redacts or rejects secrets and sensitive credentials from memory candidates."""

    @classmethod
    def scan_for_violations(cls, content: str) -> list[str]:
        """Scan text for disallowed secret or credential patterns, returning list of detected types."""
        violations: list[str] = []
        for pattern, name in SECRET_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(name)
        return violations

    @classmethod
    def enforce(cls, content: str) -> None:
        """Raise MemoryPrivacyViolationError if prohibited secrets are detected."""
        violations = cls.scan_for_violations(content)
        if violations:
            raise MemoryPrivacyViolationError(
                f"Memory content contains prohibited sensitive data: {', '.join(violations)}",
                detected_types=violations,
            )

    @classmethod
    def sanitize(cls, content: str) -> str:
        """Mask detected sensitive patterns in text."""
        sanitized = content
        for pattern, name in SECRET_PATTERNS:
            sanitized = re.sub(
                pattern, f"[REDACTED_{name.upper()}]", sanitized, flags=re.IGNORECASE
            )
        return sanitized


class MemoryAccessPolicy:
    """Verifies tenant isolation, visibility rules, and status checks on memory records."""

    @staticmethod
    def authorize_read(
        memory_item: Any,
        caller_org_id: uuid.UUID,
        caller_user_id: uuid.UUID | None = None,
        caller_session_id: uuid.UUID | None = None,
        user_permissions: set[str] | None = None,
    ) -> None:
        """Ensure caller is authorized to view the memory item within strict tenant and privacy scopes."""
        # 1. Tenant Isolation (Absolute boundary)
        if memory_item.organization_id != caller_org_id:
            raise MemoryAccessDeniedError(
                memory_item.id,
                "Cross-tenant memory access is strictly prohibited.",
            )

        # 2. Status check
        if memory_item.status == MemoryStatus.DELETED.value:
            raise MemoryAccessDeniedError(
                memory_item.id,
                "Memory item has been deleted.",
            )

        # 3. Visibility boundaries
        vis = memory_item.visibility
        perms = user_permissions or set()

        if (
            vis in (MemoryVisibility.PRIVATE.value, MemoryVisibility.USER.value)
            and (caller_user_id is None or memory_item.user_id != caller_user_id)
            and "memory.admin" not in perms
        ):
            raise MemoryAccessDeniedError(
                memory_item.id,
                f"Memory item has '{vis}' visibility and is restricted to its owner.",
            )

        if (
            vis == MemoryVisibility.SESSION.value
            and (caller_session_id is None or memory_item.session_id != caller_session_id)
            and "memory.admin" not in perms
        ):
            raise MemoryAccessDeniedError(
                memory_item.id,
                "Memory item is restricted to its origin session.",
            )

        # 4. Privacy level restrictions
        if (
            memory_item.privacy_level == MemoryPrivacyLevel.RESTRICTED.value
            and "memory.admin" not in perms
        ):
            raise MemoryAccessDeniedError(
                memory_item.id,
                "Memory item is classified as RESTRICTED requiring memory.admin permission.",
            )

    @staticmethod
    def authorize_write(
        privacy_level: Any,
        user_permissions: set[str] | None = None,
    ) -> None:
        """Ensure caller is authorized to create or update memory with specified privacy level."""
        perms = user_permissions or set()
        p_val = privacy_level.value if hasattr(privacy_level, "value") else str(privacy_level)
        if p_val == MemoryPrivacyLevel.RESTRICTED.value and "memory.admin" not in perms:
            raise MemoryAccessDeniedError(
                uuid.uuid4(),
                "Creating or updating RESTRICTED memory requires memory.admin permission.",
            )
