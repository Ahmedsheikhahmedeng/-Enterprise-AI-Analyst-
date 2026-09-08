"""Domain exceptions hierarchy for Query Understanding and Planning."""


class QueryUnderstandingError(Exception):
    """Base exception for all query understanding and processing errors."""


class QueryValidationError(QueryUnderstandingError):
    """Raised when a user query fails structural, length, or boundary validation."""


class QuerySafetyError(QueryUnderstandingError):
    """Raised when an adversarial pattern or unsafe control tokens are detected."""


class QueryTimeoutError(QueryUnderstandingError):
    """Raised when query understanding or LLM analysis exceeds its allocated latency budget."""


class QueryProviderError(QueryUnderstandingError):
    """Raised when an underlying query analysis provider (e.g. LLM or local model) fails."""


class QueryBudgetExceededError(QueryUnderstandingError):
    """Raised when generated query alternatives exceed configured safety ceilings."""
