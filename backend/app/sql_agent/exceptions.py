"""Domain exceptions for Secure SQL Agent & Structured Data Analysis."""


class SQLAgentError(Exception):
    """Base exception for all SQL Agent errors."""


class SQLValidationError(SQLAgentError):
    """Raised when generated SQL is syntactically invalid or fails basic checks."""


class SQLSecurityViolationError(SQLAgentError):
    """Raised when generated SQL attempts unauthorized operations or violates safety bounds."""


class SQLTimeoutError(SQLAgentError):
    """Raised when SQL execution exceeds database or application timeout thresholds."""


class SQLTenantMismatchError(SQLAgentError):
    """Raised when a request attempts to access data sources belonging to another tenant."""


class SQLDataSourceNotFoundError(SQLAgentError):
    """Raised when requested data source or its schema cannot be found."""


class SQLResultSizeExceededError(SQLAgentError):
    """Raised when query execution exceeds maximum permitted row count or byte size."""


class SQLProviderError(SQLAgentError):
    """Raised when the underlying SQL generation provider encounters an error."""


class SQLConfigurationError(SQLAgentError):
    """Raised when SQL Agent is improperly configured or missing credentials."""
