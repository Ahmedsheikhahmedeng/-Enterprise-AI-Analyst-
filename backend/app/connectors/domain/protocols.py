"""Protocols defining the standard interfaces for enterprise data connectors."""

import uuid
from typing import Any, Protocol, runtime_checkable

from app.connectors.domain.capabilities import ConnectorCapabilities
from app.connectors.domain.models import (
    ConnectionTestResult,
    PreviewResult,
    QueryRequest,
    QueryResult,
    SchemaModel,
)


@runtime_checkable
class SchemaProvider(Protocol):
    """Protocol for discovering relational or tabular schema definitions."""

    async def get_schema(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
    ) -> SchemaModel:
        """Discover and return normalized schema model."""
        ...


@runtime_checkable
class QueryProvider(Protocol):
    """Protocol for executing analytical read-only queries."""

    async def execute_query(
        self,
        request: QueryRequest,
        config: dict[str, Any],
    ) -> QueryResult:
        """Execute query bounded by timeout and max_rows."""
        ...

    async def preview_data(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
        target_name: str | None = None,
        max_rows: int = 50,
    ) -> PreviewResult:
        """Return safe bounded preview sample."""
        ...


@runtime_checkable
class SyncProvider(Protocol):
    """Protocol for full or incremental synchronization."""

    async def run_sync(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
        sync_type: str = "full",
    ) -> dict[str, Any]:
        """Perform synchronization and return operational metadata (rows synced, etc.)."""
        ...


@runtime_checkable
class DataConnector(Protocol):
    """Unified protocol that all enterprise connectors must satisfy."""

    @property
    def capabilities(self) -> ConnectorCapabilities:
        """Return the immutable capability flags of this connector."""
        ...

    async def test_connection(
        self,
        config: dict[str, Any],
        timeout_seconds: float = 10.0,
    ) -> ConnectionTestResult:
        """Test live connectivity without leaking raw credentials."""
        ...

    async def get_schema(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
    ) -> SchemaModel:
        """Discover schema if supported."""
        ...

    async def execute_query(
        self,
        request: QueryRequest,
        config: dict[str, Any],
    ) -> QueryResult:
        """Execute read-only query if supported."""
        ...

    async def preview_data(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
        target_name: str | None = None,
        max_rows: int = 50,
    ) -> PreviewResult:
        """Preview tabular sample if supported."""
        ...

    async def health_check(
        self,
        config: dict[str, Any],
    ) -> bool:
        """Fast liveness check."""
        ...
