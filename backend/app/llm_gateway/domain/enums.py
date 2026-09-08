"""Domain enums for Enterprise LLM Gateway and Model Governance."""

from enum import StrEnum


class LLMTaskType(StrEnum):
    """Categorization of AI generation tasks driving model routing and budgeting."""

    RAG_ANSWER = "rag_answer"
    SQL_GENERATION = "sql_generation"
    ANALYST_REASONING = "analyst_reasoning"
    AGENT_REASONING = "agent_reasoning"
    EVALUATION_JUDGE = "evaluation_judge"
    QUERY_REWRITE = "query_rewrite"
    SEMANTIC_REASONING = "semantic_reasoning"
    GRAPH_REASONING = "graph_reasoning"
    REPORT_GENERATION = "report_generation"
    FINAL_RESPONSE_GENERATION = "final_response_generation"


class ModelCapability(StrEnum):
    """Controlled capability classifications supported by registered LLM models."""

    CHAT = "chat"
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_CALLING = "tool_calling"
    JSON_MODE = "json_mode"
    VISION = "vision"
    LONG_CONTEXT = "long_context"
    STREAMING = "streaming"
    EMBEDDING = "embedding"


class RoutingStrategy(StrEnum):
    """Deterministic model selection optimization policies."""

    QUALITY_FIRST = "quality_first"
    BALANCED = "balanced"
    COST_FIRST = "cost_first"
    LATENCY_FIRST = "latency_first"


class CircuitBreakerState(StrEnum):
    """Operational states for provider circuit breakers."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class DataSensitivity(StrEnum):
    """Data residency and sensitivity classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class InputTrustLevel(StrEnum):
    """Input boundary provenance levels preventing prompt injection elevation."""

    USER_INPUT = "user_input"
    DOCUMENT_CONTENT = "document_content"
    DATABASE_CONTENT = "database_content"
    MEMORY_CONTENT = "memory_content"
    SYSTEM_INSTRUCTION = "system_instruction"


class ModelStatus(StrEnum):
    """Lifecycle status of models in the registry."""

    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    DISABLED = "DISABLED"


class FallbackReason(StrEnum):
    """Eligible conditions permitting automatic failover to secondary models."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    PROVIDER_ERROR = "provider_error"
    INVALID_RESPONSE = "invalid_response"
    CAPABILITY_MISMATCH = "capability_mismatch"
    BUDGET_EXCEEDED = "budget_exceeded"


class MessageRole(StrEnum):
    """Message role types in chat conversations."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class StreamChunkType(StrEnum):
    """Chunk event classifications for token streaming abstractions."""

    TOKEN = "token"
    USAGE = "usage"
    FINAL = "final"
    ERROR = "error"
