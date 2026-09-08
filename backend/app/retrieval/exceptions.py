"""Exception hierarchy for retrieval operations."""

from typing import Any


class RetrievalError(Exception):
    """Base exception for all retrieval operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidQueryError(RetrievalError):
    """Raised when the search query violates constraints (empty, length, tokens)."""

    pass


class RetrievalValidationError(RetrievalError):
    """Raised when search parameters or filters fail validation checks."""

    pass


class RetrievalTenantError(RetrievalError):
    """Raised when tenant context is missing or tenant isolation invariants are violated."""

    pass


class VectorSearchError(RetrievalError):
    """Raised when vector similarity search against the vector store provider fails."""

    pass


class RetrievalTimeoutError(RetrievalError):
    """Raised when retrieval operations exceed maximum allowable execution time."""

    pass
