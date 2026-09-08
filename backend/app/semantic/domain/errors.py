"""Domain exceptions for Semantic Catalog, Metrics, and Governance."""

import uuid
from typing import Any


class SemanticError(Exception):
    """Base domain exception for semantic operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SemanticObjectNotFoundError(SemanticError):
    """Raised when a requested semantic concept is not found in the tenant catalog."""

    def __init__(self, object_type: str, object_id: uuid.UUID | str) -> None:
        super().__init__(
            f"Semantic {object_type} '{object_id}' not found.",
            {"object_type": object_type, "object_id": str(object_id)},
        )


class SemanticConflictError(SemanticError):
    """Raised when conflicting business definitions or contradictory formulas are detected."""

    def __init__(self, reason: str, object_ids: list[str]) -> None:
        super().__init__(
            f"Semantic conflict detected: {reason}",
            {"reason": reason, "object_ids": object_ids},
        )


class InvalidMetricFormulaError(SemanticError):
    """Raised when a metric expression fails AST validation or attempts malicious injection."""

    def __init__(self, formula: str, reason: str) -> None:
        super().__init__(
            f"Invalid metric formula '{formula}': {reason}",
            {"formula": formula, "reason": reason},
        )


class UnauthorizedSemanticActionError(SemanticError):
    """Raised when an operation attempts to bypass semantic review or publishing controls."""

    def __init__(self, action: str, reason: str) -> None:
        super().__init__(
            f"Unauthorized semantic action '{action}': {reason}",
            {"action": action, "reason": reason},
        )


class UnverifiedSemanticObjectError(SemanticError):
    """Raised when an execution requires verified mappings but unverified links are present."""

    def __init__(self, object_id: uuid.UUID | str) -> None:
        super().__init__(
            f"Semantic object '{object_id}' is unverified and cannot be used as authoritative truth.",
            {"object_id": str(object_id)},
        )
