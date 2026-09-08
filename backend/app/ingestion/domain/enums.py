"""Domain enums for dataset ingestion, materialization, profiling, and quality."""

from enum import StrEnum


class DatasetStatus(StrEnum):
    """Lifecycle states of a Dataset."""

    CREATED = "created"
    INGESTING = "ingesting"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"
    ARCHIVED = "archived"


class IngestionStage(StrEnum):
    """Execution stages during dataset ingestion pipeline."""

    PENDING = "pending"
    RUNNING = "running"
    VALIDATING = "validating"
    PROFILING = "profiling"
    NORMALIZING = "normalizing"
    MATERIALIZING = "materializing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeduplicationStrategy(StrEnum):
    """Supported deduplication strategies."""

    EXACT_ROW_HASH = "exact_row_hash"
    PRIMARY_KEY = "primary_key"
    COMPOSITE_KEY = "composite_key"
    NONE = "none"


class IngestionMode(StrEnum):
    """Ingestion modality controlling downstream indexing."""

    STRUCTURED_ONLY = "structured_only"
    RAG_ENABLED = "rag_enabled"
    BOTH = "both"


class PIIClassification(StrEnum):
    """Detected PII pattern category."""

    NONE = "none"
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    NATIONAL_ID = "national_id"


class DataClassification(StrEnum):
    """Dataset and column security classification level."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"


class ColumnDataType(StrEnum):
    """Standardized dataset column data types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    DECIMAL = "decimal"
    NULL = "null"
    UNKNOWN = "unknown"
