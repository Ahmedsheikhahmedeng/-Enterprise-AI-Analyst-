"""Domain enumerations for Enterprise AI Response & Decision Orchestration."""

from enum import StrEnum


class OrchestrationMode(StrEnum):
    """Execution mode requested by client or resolved by system."""

    AUTO = "AUTO"
    RAG = "RAG"
    SQL = "SQL"
    HYBRID = "HYBRID"
    GRAPH = "GRAPH"


class OrchestrationStatus(StrEnum):
    """Comprehensive lifecycle states for end-to-end orchestration execution."""

    RECEIVED = "RECEIVED"
    UNDERSTANDING = "UNDERSTANDING"
    SEMANTIC_RESOLUTION = "SEMANTIC_RESOLUTION"
    GRAPH_REASONING = "GRAPH_REASONING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    COLLECTING_EVIDENCE = "COLLECTING_EVIDENCE"
    VERIFYING = "VERIFYING"
    DECIDING = "DECIDING"
    GENERATING_RESPONSE = "GENERATING_RESPONSE"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionStrategy(StrEnum):
    """Targeted branch routing strategy determined by the reasoning planner."""

    RAG_ONLY = "RAG_ONLY"
    SQL_ONLY = "SQL_ONLY"
    GRAPH_ONLY = "GRAPH_ONLY"
    HYBRID = "HYBRID"
    NONE = "NONE"


class EvidenceTrustLevel(StrEnum):
    """Hierarchical classification of evidence veracity."""

    DIRECT = "DIRECT"  # Verified database rows, exact document chunks
    DERIVED = "DERIVED"  # Aggregate metrics, verified calculations
    INFERRED = "INFERRED"  # Multi-hop graph path deductions
    UNVERIFIED = "UNVERIFIED"  # Untrusted external data or non-authoritative memory
    CONFLICTING = "CONFLICTING"  # Contradicts another source


class EvidenceSourceType(StrEnum):
    """Origin of gathered evidence item."""

    DOCUMENT = "document"
    SQL = "sql"
    GRAPH = "graph"
    SEMANTIC = "semantic"
    MEMORY = "memory"


class ClaimStatus(StrEnum):
    """Verification outcome of an extracted factual assertion."""

    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


class DecisionType(StrEnum):
    """Actionable analytical resolution determined by the decision engine."""

    ANSWER = "ANSWER"
    ANSWER_WITH_WARNING = "ANSWER_WITH_WARNING"
    PARTIAL_ANSWER = "PARTIAL_ANSWER"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCK = "BLOCK"


class ResponseStyle(StrEnum):
    """Output formatting tone and granularity constraint."""

    CONCISE = "CONCISE"
    STANDARD = "STANDARD"
    DETAILED = "DETAILED"
    EXECUTIVE = "EXECUTIVE"
