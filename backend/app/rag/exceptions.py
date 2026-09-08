"""Domain exceptions hierarchy for evidence-grounded RAG."""


class RAGError(Exception):
    """Base exception for all RAG and generation domain errors."""


class RAGConfigurationError(RAGError):
    """Raised when RAG parameters, models, or API keys are misconfigured."""


class RAGTenantMismatchError(RAGError):
    """Raised when evidence candidates do not belong to the invoking organization."""


class RAGContextOverflowError(RAGError):
    """Raised when retrieved evidence exceeds configured token context ceilings."""


class RAGGroundingError(RAGError):
    """Raised when generated response fails citation or factual grounding validation."""


class RAGProviderError(RAGError):
    """Raised when underlying LLM provider or external generation service fails."""


class RAGTimeoutError(RAGError):
    """Raised when LLM answer generation exceeds allocated timeout budget."""
