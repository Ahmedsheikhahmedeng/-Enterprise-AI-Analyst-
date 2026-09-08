"""RAG and Answer Generation domain package."""

from app.rag.config import RAGConfig, get_rag_config
from app.rag.context import ContextAssembler
from app.rag.evidence import EvidenceSelector
from app.rag.exceptions import (
    RAGConfigurationError,
    RAGContextOverflowError,
    RAGError,
    RAGGroundingError,
    RAGProviderError,
    RAGTenantMismatchError,
    RAGTimeoutError,
)
from app.rag.grounding import GroundingValidator
from app.rag.models import (
    CitationReference,
    Evidence,
    GroundedAnswer,
    RAGAnswerResult,
    RAGDiagnostics,
    RAGEvent,
    RAGEventType,
)
from app.rag.prompts import PromptBuilder
from app.rag.service import RAGService

__all__ = [
    "CitationReference",
    "ContextAssembler",
    "Evidence",
    "EvidenceSelector",
    "GroundedAnswer",
    "GroundingValidator",
    "PromptBuilder",
    "RAGAnswerResult",
    "RAGConfig",
    "RAGConfigurationError",
    "RAGContextOverflowError",
    "RAGDiagnostics",
    "RAGError",
    "RAGEvent",
    "RAGEventType",
    "RAGGroundingError",
    "RAGProviderError",
    "RAGService",
    "RAGTenantMismatchError",
    "RAGTimeoutError",
    "get_rag_config",
]
