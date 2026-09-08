"""Domain exceptions for Enterprise Data Connectors & Unified Access Layer."""

import uuid
from typing import Any


class ConnectorError(Exception):
    """Base exception for all connector-related errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConnectionFailedError(ConnectorError):
    """Raised when testing or establishing a live connection fails."""

    def __init__(self, datasource_id: uuid.UUID | str, reason: str) -> None:
        super().__init__(
            f"Failed connecting to data source '{datasource_id}': {reason}",
            {"datasource_id": str(datasource_id), "reason": reason},
        )


class SchemaDiscoveryError(ConnectorError):
    """Raised when discovering or parsing data source schemas fails."""

    def __init__(self, datasource_id: uuid.UUID | str, reason: str) -> None:
        super().__init__(
            f"Failed discovering schema for data source '{datasource_id}': {reason}",
            {"datasource_id": str(datasource_id), "reason": reason},
        )


class QueryExecutionError(ConnectorError):
    """Raised when executing a query against the connector fails."""

    def __init__(
        self, datasource_id: uuid.UUID | str, reason: str, query_snippet: str | None = None
    ) -> None:
        super().__init__(
            f"Query execution failed on data source '{datasource_id}': {reason}",
            {"datasource_id": str(datasource_id), "reason": reason, "query_snippet": query_snippet},
        )


class QueryTimeoutError(QueryExecutionError):
    """Raised when query execution exceeds configured timeout bound."""

    def __init__(self, datasource_id: uuid.UUID | str, timeout_ms: int) -> None:
        super().__init__(
            datasource_id=datasource_id,
            reason=f"Query exceeded execution timeout limit of {timeout_ms}ms.",
        )


class ResultSizeExceededError(QueryExecutionError):
    """Raised when query returns more rows or bytes than permitted."""

    def __init__(self, datasource_id: uuid.UUID | str, max_rows: int) -> None:
        super().__init__(
            datasource_id=datasource_id,
            reason=f"Query result row count exceeded ceiling of {max_rows} rows.",
        )


class SyncError(ConnectorError):
    """Raised when background synchronization fails."""

    def __init__(self, datasource_id: uuid.UUID | str, reason: str) -> None:
        super().__init__(
            f"Sync failed for data source '{datasource_id}': {reason}",
            {"datasource_id": str(datasource_id), "reason": reason},
        )


class UnsupportedCapabilityError(ConnectorError):
    """Raised when requesting an operation not supported by connector capabilities."""

    def __init__(self, capability: str, reason: str) -> None:
        super().__init__(
            f"Capability '{capability}' is unsupported: {reason}",
            {"capability": capability, "reason": reason},
        )


class DataSourceNotFoundError(ConnectorError):
    """Raised when a requested data source does not exist within the tenant boundary."""

    def __init__(self, datasource_id: uuid.UUID | str) -> None:
        super().__init__(
            f"Data source '{datasource_id}' not found or access is denied.",
            {"datasource_id": str(datasource_id)},
        )


class InvalidConfigurationError(ConnectorError):
    """Raised when connector configuration payload fails structural or security validation."""

    def __init__(self, connector_type: str, reason: str) -> None:
        super().__init__(
            f"Invalid configuration for connector '{connector_type}': {reason}",
            {"connector_type": connector_type, "reason": reason},
        )


class SecretDecryptionError(ConnectorError):
    """Raised when decrypting sensitive connection parameters fails."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Secret decryption failed: {reason}", {"reason": reason})


class FileProcessingError(ConnectorError):
    """Raised when file parsing (CSV, Excel) encounters malformed structures or corruption."""

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(
            f"Error processing file '{filename}': {reason}",
            {"filename": filename, "reason": reason},
        )


class FormulaInjectionError(ConnectorError):
    """Raised when spreadsheet formulas attempt CSV/Excel formula injection (=, +, -, @)."""

    def __init__(self, cell_content: str) -> None:
        super().__init__(
            "Formula injection pattern detected in data content.",
            {"cell_snippet": cell_content[:50]},
        )
