from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from app.response_orchestration.domain.enums import DecisionType
from app.response_orchestration.domain.models import (
    Claim,
    EnterpriseQueryRequest,
    EnterpriseResponse,
    EvidenceBundle,
    EvidenceConflict,
    UnifiedReasoningPlan,
)

if TYPE_CHECKING:
    from app.tenancy.context import TenantContext


@runtime_checkable
class ConfidenceScorerProtocol(Protocol):
    """Protocol for computing calibrated confidence scores."""

    def calculate_confidence(
        self,
        evidence_bundle: EvidenceBundle,
        conflicts: list[EvidenceConflict],
        claims: list[Claim],
        semantic_confidence: float,
        graph_confidence: float,
    ) -> float: ...


@runtime_checkable
class ConflictDetectorProtocol(Protocol):
    """Protocol for detecting contradictions across multi-source evidence."""

    def detect_conflicts(self, evidence_bundle: EvidenceBundle) -> list[EvidenceConflict]: ...


@runtime_checkable
class DecisionServiceProtocol(Protocol):
    """Protocol for determining final response actions and policies."""

    def evaluate_decision(
        self,
        plan: UnifiedReasoningPlan,
        evidence_bundle: EvidenceBundle,
        conflicts: list[EvidenceConflict],
        claims: list[Claim],
        confidence_score: float,
        evidence_coverage: float,
        branch_failures: list[str],
    ) -> DecisionType: ...


@runtime_checkable
class ResponseOrchestrationProtocol(Protocol):
    """Canonical interface for enterprise response orchestration."""

    async def ask(
        self,
        request: EnterpriseQueryRequest,
        *,
        session: AsyncSession,
        tenant_context: "TenantContext | None" = None,
    ) -> EnterpriseResponse: ...
