"""Calibrated confidence scoring service evaluating multi-source evidence and verification signals."""

import logging

from app.response_orchestration.domain.enums import ClaimStatus, EvidenceTrustLevel
from app.response_orchestration.domain.models import (
    Claim,
    EvidenceBundle,
    EvidenceConflict,
)
from app.response_orchestration.domain.protocols import ConfidenceScorerProtocol

logger = logging.getLogger(__name__)


class ConfidenceService(ConfidenceScorerProtocol):
    """Calculates a deterministic confidence score in [0.0, 1.0] from empirical signals."""

    # Weights configuration
    W_EVIDENCE_COVERAGE = 0.35
    W_TRUST_TIER = 0.25
    W_SEMANTIC = 0.20
    W_GRAPH = 0.10
    W_CITATION_VALIDITY = 0.10

    # Trust level multiplier weights
    TRUST_MULTIPLIERS = {
        EvidenceTrustLevel.DIRECT: 1.0,
        EvidenceTrustLevel.DERIVED: 0.85,
        EvidenceTrustLevel.INFERRED: 0.65,
        EvidenceTrustLevel.UNVERIFIED: 0.20,
        EvidenceTrustLevel.CONFLICTING: 0.0,
    }

    def calculate_confidence(
        self,
        evidence_bundle: EvidenceBundle,
        conflicts: list[EvidenceConflict],
        claims: list[Claim],
        semantic_confidence: float = 0.0,
        graph_confidence: float = 0.0,
    ) -> float:
        """Compute holistic confidence score reflecting ground truth reliability."""
        if not evidence_bundle.items:
            return 0.0

        # 1. Evidence coverage: supported claims / total claims
        if claims:
            supported = sum(
                1.0
                for c in claims
                if c.status in (ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED)
            )
            coverage = supported / len(claims)
        else:
            coverage = 0.85  # baseline if claims not yet extracted

        # 2. Source trust tier average
        trust_scores = [
            self.TRUST_MULTIPLIERS.get(it.trust_level, 0.5) * max(0.0, min(it.confidence, 1.0))
            for it in evidence_bundle.items
        ]
        avg_trust = sum(trust_scores) / len(trust_scores) if trust_scores else 0.5

        # 3. Citation validity (penalize if claims refer to nonexistent evidence)
        claimed_ids = {cit for cl in claims for cit in cl.citations_claimed}
        valid_ids = {it.citation_id for it in evidence_bundle.items if it.citation_id}
        if claimed_ids:
            valid_ratio = len(claimed_ids.intersection(valid_ids)) / len(claimed_ids)
        else:
            valid_ratio = 1.0

        # 4. Conflict penalty
        conflict_penalty = 0.0
        for conf in conflicts:
            if conf.severity == "critical":
                conflict_penalty += 0.35
            elif conf.severity == "high":
                conflict_penalty += 0.20
            elif conf.severity == "medium":
                conflict_penalty += 0.10
            else:
                conflict_penalty += 0.05
        conflict_penalty = min(0.60, conflict_penalty)

        # 5. Weighted aggregation
        base_score = (
            (coverage * self.W_EVIDENCE_COVERAGE)
            + (avg_trust * self.W_TRUST_TIER)
            + (max(0.0, min(semantic_confidence, 1.0)) * self.W_SEMANTIC)
            + (max(0.0, min(graph_confidence, 1.0)) * self.W_GRAPH)
            + (valid_ratio * self.W_CITATION_VALIDITY)
        )

        final_score = max(0.0, min(base_score - conflict_penalty, 1.0))
        return round(final_score, 4)
