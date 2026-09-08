"""Domain models for unified execution planning, evidence merging, and analysis."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class AnalystRouteType(StrEnum):
    """Categorization of data modality targeted by the user query."""

    RAG = "rag"
    SQL = "sql"
    HYBRID = "hybrid"
    NONE = "none"


class BranchType(StrEnum):
    """Target subsystem executing a distinct branch of the execution plan."""

    RAG = "rag"
    SQL = "sql"


@dataclass(frozen=True)
class ExecutionBranch:
    """Independent actionable branch of an Analyst ExecutionPlan."""

    branch_id: str
    branch_type: BranchType
    query: str
    datasource_id: UUID | None = None
    limit: int | None = None
    top_k: int | None = None
    timeout_seconds: float = 10.0


@dataclass
class ExecutionPlan:
    """Deterministic or planned execution strategy for answering an analyst query."""

    plan_id: UUID
    original_query: str
    route: AnalystRouteType
    confidence: float
    branches: list[ExecutionBranch] = field(default_factory=list)
    requires_final_generation: bool = True
    reason: str = ""
    budget_max_evidence: int = 20


@dataclass
class UnifiedEvidence:
    """Consolidated evidence item harmonizing structured SQL and unstructured RAG sources."""

    evidence_id: str  # e.g. "S1", "S2" for SQL; "R1", "R2" for RAG
    source_type: str  # "sql" or "document"
    title: str  # table name or document title
    text: str  # formatted data record / aggregation summary or text chunk
    is_calculated: bool  # True for calculated SQL results; False for document quotes
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class DataConflict:
    """Identified factual or numerical contradiction between distinct evidence sources."""

    field: str
    source_a: str
    value_a: Any
    source_b: str
    value_b: Any
    severity: str  # "low", "medium", "high"
    description: str


@dataclass
class AnalystBranchResult:
    """Outcome of an individual executed plan branch."""

    branch_id: str
    branch_type: BranchType
    success: bool
    data: Any = None
    evidence: list[UnifiedEvidence] = field(default_factory=list)
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class AnalystDiagnostics:
    """Observability metrics detailing execution timing, token accounting, and costs."""

    planning_ms: float = 0.0
    sql_ms: float = 0.0
    rag_ms: float = 0.0
    merge_ms: float = 0.0
    conflict_ms: float = 0.0
    generation_ms: float = 0.0
    total_ms: float = 0.0
    route_selected: str = "none"
    branches_executed: int = 0
    sql_cost_usd: float = 0.0
    rag_cost_usd: float = 0.0
    generation_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    degraded: bool = False
    degradation_reason: str | None = None


@dataclass
class AnalystResult:
    """Final grounded analysis result returned by AIAnalystService."""

    answer: str
    route: AnalystRouteType
    grounded: bool
    confidence: float
    is_partial: bool = False
    is_degraded: bool = False
    conflicts: list[DataConflict] = field(default_factory=list)
    evidence: list[UnifiedEvidence] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: AnalystDiagnostics = field(default_factory=AnalystDiagnostics)
    execution_plan: ExecutionPlan | None = None
    analysis_run_id: UUID | None = None
