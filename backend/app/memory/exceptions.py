"""Domain exceptions for Enterprise Agent Memory."""

from typing import Any
from uuid import UUID


class MemoryError(Exception):
    """Base exception for all agent memory errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class MemoryNotFoundError(MemoryError):
    """Raised when a requested memory item does not exist or has been deleted."""

    def __init__(self, memory_id: UUID) -> None:
        super().__init__(
            f"Memory item '{memory_id}' not found.",
            {"memory_id": str(memory_id)},
        )


class MemoryAccessDeniedError(MemoryError):
    """Raised when access to a memory item is denied due to tenant or visibility mismatch."""

    def __init__(self, memory_id: UUID, reason: str) -> None:
        super().__init__(
            f"Access denied to memory item '{memory_id}': {reason}",
            {"memory_id": str(memory_id), "reason": reason},
        )


class MemoryPrivacyViolationError(MemoryError):
    """Raised when content contains disallowed sensitive data, credentials, or PII."""

    def __init__(self, reason: str, detected_types: list[str] | None = None) -> None:
        super().__init__(
            f"Memory privacy violation: {reason}",
            {"reason": reason, "detected_types": detected_types or []},
        )


class MemoryConflictError(MemoryError):
    """Raised when memory candidate directly conflicts with existing active memory."""

    def __init__(self, message: str, existing_memory_id: UUID | None = None) -> None:
        super().__init__(
            f"Memory conflict detected: {message}",
            {"existing_memory_id": str(existing_memory_id) if existing_memory_id else None},
        )


class MemoryBudgetExceededError(MemoryError):
    """Raised when an organization or user memory limit is exceeded."""

    def __init__(self, limit_type: str, limit_val: int) -> None:
        super().__init__(
            f"Memory budget exceeded for '{limit_type}': limit is {limit_val}.",
            {"limit_type": limit_type, "limit": limit_val},
        )


class MemoryValidationError(MemoryError):
    """Raised when memory content or metadata fails schema validation."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Memory validation failed: {message}")
