"""Vector store exception hierarchy."""

from typing import Any


class VectorStoreError(Exception):
    """Base exception for all vector store operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class VectorStoreConfigurationError(VectorStoreError):
    """Raised when vector store configuration parameters are invalid or missing."""

    pass


class VectorStoreConnectionError(VectorStoreError):
    """Raised when vector database cluster cannot be contacted."""

    pass


class VectorStoreTimeoutError(VectorStoreConnectionError):
    """Raised when an operation against the vector database exceeds timeout."""

    pass


class VectorStoreValidationError(VectorStoreError):
    """Raised when points, vectors, or payloads fail invariant checks."""

    pass


class CollectionMismatchError(VectorStoreConfigurationError):
    """Raised when an existing collection vector dimensions or distance metric mismatch."""

    def __init__(
        self,
        collection_name: str,
        expected_size: int,
        actual_size: int,
        expected_distance: str,
        actual_distance: str,
    ) -> None:
        msg = (
            f"Collection '{collection_name}' configuration mismatch: "
            f"expected (size={expected_size}, distance={expected_distance}), "
            f"got (size={actual_size}, distance={actual_distance})."
        )
        super().__init__(
            msg,
            details={
                "collection_name": collection_name,
                "expected_size": expected_size,
                "actual_size": actual_size,
                "expected_distance": expected_distance,
                "actual_distance": actual_distance,
            },
        )


class TenantIsolationError(VectorStoreError):
    """Raised when cross-tenant boundary violations are detected during vector store operations."""

    pass
