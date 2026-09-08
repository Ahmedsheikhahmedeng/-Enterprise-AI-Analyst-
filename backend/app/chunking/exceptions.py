"""Custom exceptions for the document chunking subsystem."""

from typing import Any


class ChunkingError(Exception):
    """Base exception for all chunking-related failures."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ChunkingValidationError(ChunkingError):
    """Raised when generated chunks fail quality or boundary validation checks."""


class ChunkingLimitError(ChunkingError):
    """Raised when document content or element sizes exceed safety limits."""


class ChunkingPersistenceError(ChunkingError):
    """Raised when database operations fail during chunk persistence or reprocessing."""
