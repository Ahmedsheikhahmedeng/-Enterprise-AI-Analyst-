"""Domain errors and exceptions for Dataset Ingestion and Materialization."""


class DatasetError(Exception):
    """Base exception for all dataset and ingestion errors."""


class DatasetNotFoundError(DatasetError):
    """Raised when a requested dataset is not found for the tenant."""


class DatasetNotReadyError(DatasetError):
    """Raised when an operation attempts to use a dataset not in READY status."""


class DatasetAlreadyExistsError(DatasetError):
    """Raised when a dataset with identical identity or name exists."""


class InvalidSchemaError(DatasetError):
    """Raised when incoming dataset schema violates validation bounds."""


class ProfilingError(DatasetError):
    """Raised when statistical profiling fails."""


class NormalizationError(DatasetError):
    """Raised when column or data normalization fails."""


class DeduplicationError(DatasetError):
    """Raised when deduplication fails."""


class MaterializationError(DatasetError):
    """Raised when persisting or materializing dataset storage fails."""


class LineageError(DatasetError):
    """Raised when lineage tracking or fingerprint computation fails."""


class DataQualityError(DatasetError):
    """Raised when data quality checks fail or score computation error."""
