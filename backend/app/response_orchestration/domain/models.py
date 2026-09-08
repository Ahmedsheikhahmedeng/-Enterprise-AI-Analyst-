"""Domain models and data schemas for Enterprise Response Orchestration."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.response_orchestration.domain.enums import (
    ClaimStatus,
    DecisionType,
    EvidenceSourceType,
    EvidenceTrustLevel,
    ExecutionStrategy,
    OrchestrationMode,
    OrchestrationStatus,
    ResponseStyle,
)


@dataclass(frozen=True)
class EnterpriseQueryRequest:
    """Canonical invocation request for the unified enterprise query orchestrator."""

    question: str
    organization_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    mode: OrchestrationMode = OrchestrationMode.AUTO
    response_style: ResponseStyle = ResponseStyle.STANDARD
    target_dataset_id: uuid.UUID | None = None
    max_execution_time_sec: float = 30.0
    enable_clarification: bool = True
    session_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationItem:
    """Normalized citation pointing to a verifiable evidence record."""

    citation_id: str  # e.g. '[D1]', '[S1]', '[G1]', '[M1]'
    source_type: EvidenceSourceType
    source_id: str
    title: str
    snippet: str
    trust_level: EvidenceTrustLevel
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    """Atomic piece of factual evidence collected from platform subsystems."""

    evidence_id: str
    source_type: EvidenceSourceType
    source_id: str
    content: str
    trust_level: EvidenceTrustLevel
    confidence: float
    is_calculated: bool = False
    citation_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceBundle:
    """Curated collection of multi-modal evidence items."""

    items: list[EvidenceItem] = field(default_factory=list)

    def get_by_citation(self, citation_id: str) -> EvidenceItem | None:
        """Find evidence matching normalized citation id."""
        for item in self.items:
            if item.citation_id == citation_id:
                return item
        return None

    def get_by_source_type(self, source_type: EvidenceSourceType) -> list[EvidenceItem]:
        """Filter items by origin subsystem."""
        return [it for it in self.items if it.source_type == source_type]

    def has_authoritative_sql(self) -> bool:
        """Check if bundle contains direct calculated SQL facts."""
        return any(
            it.source_type == EvidenceSourceType.SQL
            and it.trust_level in (EvidenceTrustLevel.DIRECT, EvidenceTrustLevel.DERIVED)
            for it in self.items
        )


@dataclass
class EvidenceConflict:
    """Discrepancy identified between two sources."""

    conflict_id: str
    field: str
    source_a: str
    value_a: Any
    source_b: str
    value_b: Any
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    resolved_value: Any | None = None
    resolution_reason: str | None = None


@dataclass
class Claim:
    """Extracted assertion requiring grounding verification."""

    claim_id: str
    statement: str
    required_evidence_type: EvidenceSourceType | None
    citations_claimed: list[str]
    status: ClaimStatus = ClaimStatus.UNSUPPORTED
    supporting_evidence_ids: list[str] = field(default_factory=list)


@dataclass
class OrchestrationBudget:
    """Hierarchical constraints governing resource utilization during orchestration."""

    max_steps: int = 15
    max_tool_calls: int = 10
    max_llm_calls: int = 4
    max_tokens: int = 16000
    max_cost_dollars: float = 1.0
    max_execution_time_sec: float = 30.0
    max_evidence: int = 12


@dataclass
class UnifiedReasoningPlan:
    """Synthesized blueprint integrating query understanding, semantic models, and graph paths."""

    intent: str
    entities: list[str]
    resolved_metrics: list[str]
    resolved_dimensions: list[str]
    semantic_matches: list[dict[str, Any]]
    graph_paths: list[dict[str, Any]]
    candidate_datasets: list[uuid.UUID]
    execution_strategy: ExecutionStrategy
    budget: OrchestrationBudget
    requires_clarification: bool = False
    clarification_options: list[str] = field(default_factory=list)


@dataclass
class OrchestrationContext:
    """Execution state tracking across stages."""

    request_id: uuid.UUID
    trace_id: str
    organization_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None
    query: str
    budget: OrchestrationBudget
    state: OrchestrationStatus = OrchestrationStatus.RECEIVED
    state_history: list[tuple[OrchestrationStatus, datetime]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnterpriseResponse:
    """Final canonical response payload delivered to enterprise consumers."""

    execution_id: uuid.UUID
    request_id: uuid.UUID
    trace_id: str
    organization_id: uuid.UUID
    answer: str
    status: OrchestrationStatus
    decision: DecisionType
    confidence_score: float
    evidence_coverage: float
    citations: list[CitationItem] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    conflicts: list[EvidenceConflict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    clarification_prompt: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
