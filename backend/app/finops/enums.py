"""Domain enums for Enterprise FinOps, AI Cost Governance & Usage Optimization."""

from enum import StrEnum


class CostOperation(StrEnum):
    """Categorization of platform operations incurring AI model or compute cost."""

    CHAT = "CHAT"
    RAG = "RAG"
    SQL = "SQL"
    EMBEDDING = "EMBEDDING"
    RERANK = "RERANK"
    AGENT = "AGENT"
    EVALUATION = "EVALUATION"
    REPORT = "REPORT"
    MEMORY = "MEMORY"


class BudgetScope(StrEnum):
    """Hierarchical scope at which budgets are allocated and enforced."""

    ORGANIZATION = "ORGANIZATION"
    USER = "USER"
    PROJECT = "PROJECT"
    FEATURE = "FEATURE"
    AGENT = "AGENT"
    ENVIRONMENT = "ENVIRONMENT"


class BudgetPeriod(StrEnum):
    """Time cycle duration for budget limits and consumption tracking."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"


class BudgetState(StrEnum):
    """Operational state of budget based on utilization threshold."""

    SPENDING = "SPENDING"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EXHAUSTED = "EXHAUSTED"


class QuotaType(StrEnum):
    """Dimension of resource consumption bounded by a quota."""

    REQUESTS = "REQUESTS"
    TOKENS = "TOKENS"
    COST = "COST"
    CONCURRENCY = "CONCURRENCY"


class QuotaEnforcementMode(StrEnum):
    """Behavior executed when a quota threshold is exceeded."""

    ALLOW = "ALLOW"
    WARN = "WARN"
    THROTTLE = "THROTTLE"
    BLOCK = "BLOCK"


class CostEnforcementMode(StrEnum):
    """Action taken when cost policies or budget limits are violated."""

    MONITOR = "MONITOR"
    WARN = "WARN"
    THROTTLE = "THROTTLE"
    BLOCK = "BLOCK"
    APPROVAL = "APPROVAL"


class FinOpsSeverity(StrEnum):
    """Severity classification for FinOps anomalies and cost alerts."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AnomalyType(StrEnum):
    """Classification of detected financial and usage spikes."""

    SUDDEN_SPIKE = "SUDDEN_SPIKE"
    UNUSUAL_DAILY_COST = "UNUSUAL_DAILY_COST"
    UNUSUAL_TOKEN_VOLUME = "UNUSUAL_TOKEN_VOLUME"
    UNUSUAL_COST_PER_REQUEST = "UNUSUAL_COST_PER_REQUEST"
    MODEL_COST_SHIFT = "MODEL_COST_SHIFT"
    TENANT_USAGE_SPIKE = "TENANT_USAGE_SPIKE"


class RecommendationType(StrEnum):
    """Actionable FinOps efficiency recommendation types."""

    SWITCH_TO_LOWER_COST_MODEL = "SWITCH_TO_LOWER_COST_MODEL"
    REDUCE_CONTEXT = "REDUCE_CONTEXT"
    ENABLE_CACHING = "ENABLE_CACHING"
    REDUCE_MAX_OUTPUT = "REDUCE_MAX_OUTPUT"
    REVIEW_AGENT_LOOP = "REVIEW_AGENT_LOOP"
    REVIEW_RERANK_TOP_K = "REVIEW_RERANK_TOP_K"


class ReconciliationStatus(StrEnum):
    """Audit outcome when matching gateway invocations against cost ledger."""

    MATCHED = "MATCHED"
    MISSING = "MISSING"
    DUPLICATED = "DUPLICATED"
    MISMATCHED = "MISMATCHED"
    UNKNOWN_PRICING = "UNKNOWN_PRICING"


class FinOpsReadinessDecision(StrEnum):
    """Final release readiness determination based on FinOps integrity and cost risk."""

    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"


# Convenience aliases for callers
BudgetStatus = BudgetState
FinOpsReadinessStatus = FinOpsReadinessDecision
