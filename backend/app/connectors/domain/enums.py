"""Domain enums for Enterprise Data Connectors & Access Layer."""

from enum import StrEnum


class ConnectorType(StrEnum):
    """Supported data connector technologies."""

    POSTGRESQL = "postgresql"
    CSV = "csv"
    EXCEL = "excel"


class ConnectionStatus(StrEnum):
    """Lifecycle state of a DataSource connection."""

    REGISTERED = "registered"
    CONNECTING = "connecting"
    ACTIVE = "active"
    DEGRADED = "degraded"
    ERROR = "error"
    DISABLED = "disabled"


class SyncType(StrEnum):
    """Synchronization strategies."""

    FULL = "full"
    INCREMENTAL = "incremental"
    CDC = "cdc"


class SyncStatus(StrEnum):
    """State machine states for background data source synchronization."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CapabilityType(StrEnum):
    """Features and capabilities a connector can optionally provide."""

    SCHEMA_READ = "schema_read"
    QUERY = "query"
    WRITE = "write"
    SYNC = "sync"
    STREAMING = "streaming"
    CDC = "cdc"
    FILES = "files"
    EMBEDDING = "embedding"
