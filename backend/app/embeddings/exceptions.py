"""Embedding exception taxonomy."""

from typing import Any


class EmbeddingError(Exception):
    """Base exception for all embedding-related errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EmbeddingConfigurationError(EmbeddingError):
    """Raised when configuration parameters for embeddings are invalid or missing."""

    pass


class EmbeddingProviderError(EmbeddingError):
    """Raised when an external or local provider encounters an error during execution."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.provider = provider
        self.status_code = status_code


class EmbeddingAuthenticationError(EmbeddingProviderError):
    """Raised when authentication with the provider fails (e.g. invalid API key)."""

    pass


class EmbeddingRateLimitError(EmbeddingProviderError):
    """Raised when the provider rate limit or quota is exceeded."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, provider=provider, status_code=429, details=details)
        self.retry_after = retry_after


class EmbeddingTimeoutError(EmbeddingProviderError):
    """Raised when a request to the embedding provider times out."""

    pass


class EmbeddingInvalidInputError(EmbeddingError):
    """Raised when an input text or chunk is invalid, empty, or unparseable."""

    pass


class EmbeddingValidationError(EmbeddingError):
    """Raised when output vectors fail mathematical/shape/numeric validation."""

    pass


class EmbeddingDimensionError(EmbeddingValidationError):
    """Raised when returned vector dimensions do not match the expected dimensions."""

    def __init__(
        self,
        expected: int,
        actual: int,
        message: str | None = None,
    ) -> None:
        msg = message or f"Embedding dimension mismatch: expected {expected}, got {actual}"
        super().__init__(msg, details={"expected": expected, "actual": actual})
        self.expected = expected
        self.actual = actual


class EmbeddingCacheError(EmbeddingError):
    """Raised when an embedding cache operation fails unexpectedly."""

    pass
