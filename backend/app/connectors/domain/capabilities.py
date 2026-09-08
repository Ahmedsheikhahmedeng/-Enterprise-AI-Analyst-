"""Connector capability declarations and validation models."""

from pydantic import BaseModel, ConfigDict, Field


class ConnectorCapabilities(BaseModel):
    """Explicitly declares supported operations for a connector."""

    model_config = ConfigDict(frozen=True)

    schema_read: bool = Field(default=False, description="Supports metadata & schema discovery")
    query: bool = Field(default=False, description="Supports direct or translated query execution")
    write: bool = Field(default=False, description="Supports mutating operations (usually False)")
    sync: bool = Field(default=False, description="Supports background full/incremental sync")
    streaming: bool = Field(default=False, description="Supports chunked streaming data retrieval")
    cdc: bool = Field(default=False, description="Supports change data capture streams")
    files: bool = Field(default=False, description="Operates on file assets (CSV, Excel, etc.)")
    embedding: bool = Field(
        default=False, description="Supports automatic vector embedding generation"
    )

    def require_query(self) -> None:
        """Enforce that query capability is enabled."""
        if not self.query:
            from app.connectors.domain.errors import UnsupportedCapabilityError

            raise UnsupportedCapabilityError("query", "Connector does not support query execution.")

    def require_schema(self) -> None:
        """Enforce that schema_read capability is enabled."""
        if not self.schema_read:
            from app.connectors.domain.errors import UnsupportedCapabilityError

            raise UnsupportedCapabilityError(
                "schema_read", "Connector does not support schema discovery."
            )

    def require_sync(self) -> None:
        """Enforce that sync capability is enabled."""
        if not self.sync:
            from app.connectors.domain.errors import UnsupportedCapabilityError

            raise UnsupportedCapabilityError("sync", "Connector does not support synchronization.")
