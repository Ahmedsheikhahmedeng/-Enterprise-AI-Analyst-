"""Deterministic risk assessment engine for Enterprise Governance."""

import logging
from typing import Any

from app.governance.domain.enums import ApprovalType, RiskLevel
from app.governance.domain.models import RiskAssessment

logger = logging.getLogger(__name__)


class RiskService:
    """Evaluates deterministic risk rules and weighted risk scores for enterprise actions."""

    # Base risk score constants
    SCORE_LOW = 0.15
    SCORE_MEDIUM = 0.45
    SCORE_HIGH = 0.75
    SCORE_CRITICAL = 0.95

    def assess_risk(
        self,
        request_type: ApprovalType | str,
        factors: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Evaluate deterministic risk rules and calculate a calibrated risk score.

        Strict Deterministic Rules:
        - External side effects (email, external modify/delete, purchase) -> CRITICAL
        - Agent high-risk action with external or destructive capabilities -> CRITICAL
        - Policy changes & LLM Provider/Model configuration changes -> HIGH
        - Production semantic or graph publication -> HIGH
        - Bulk data export (high row count / sensitive) -> HIGH or CRITICAL
        - Read / Query on sensitive/restricted data -> MEDIUM
        - Read / Query on public data with small scope -> LOW
        """
        factors = factors or {}
        req_type = ApprovalType(request_type) if isinstance(request_type, str) else request_type
        reasons: list[str] = []

        # 1. Immediate Critical Overrides: External Side Effects
        has_external_effect = bool(factors.get("external_side_effect", False))
        operation_name = str(factors.get("operation_name", "")).lower()
        if has_external_effect or any(
            op in operation_name
            for op in [
                "send_email",
                "create_ticket",
                "purchase",
                "delete_external",
                "modify_external",
            ]
        ):
            reasons.append("Operation induces external side effects across third-party systems")
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                risk_score=self.SCORE_CRITICAL,
                reasons=reasons,
                factors=factors,
            )

        # 2. Agent High-Risk Actions
        if req_type == ApprovalType.AGENT_HIGH_RISK_ACTION:
            agent_scope = str(factors.get("scope", "ORGANIZATION")).upper()
            destructive = bool(factors.get("destructive", False))
            if destructive or agent_scope == "GLOBAL":
                reasons.append(
                    "Autonomous agent executing potentially destructive or global action"
                )
                return RiskAssessment(
                    risk_level=RiskLevel.CRITICAL,
                    risk_score=self.SCORE_CRITICAL,
                    reasons=reasons,
                    factors=factors,
                )
            reasons.append("Autonomous agent executing high-risk tenant-scoped operation")
            return RiskAssessment(
                risk_level=RiskLevel.HIGH,
                risk_score=self.SCORE_HIGH,
                reasons=reasons,
                factors=factors,
            )

        # 3. Policy & Model / Provider Changes
        if req_type in (ApprovalType.POLICY_CHANGE, ApprovalType.MODEL_CHANGE):
            reasons.append("Governance policy or core AI provider configuration mutation")
            return RiskAssessment(
                risk_level=RiskLevel.HIGH,
                risk_score=self.SCORE_HIGH,
                reasons=reasons,
                factors=factors,
            )

        # 4. Semantic & Knowledge Graph Publications
        if req_type in (ApprovalType.SEMANTIC_PUBLICATION, ApprovalType.GRAPH_PUBLICATION):
            is_production = bool(factors.get("is_production", True))
            critical_rel = bool(factors.get("critical_relationship", False))
            if is_production or critical_rel:
                reasons.append(
                    "Publication of semantic definitions or knowledge graph to production"
                )
                return RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    risk_score=self.SCORE_HIGH,
                    reasons=reasons,
                    factors=factors,
                )
            reasons.append("Draft semantic or knowledge graph publication")
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                risk_score=self.SCORE_MEDIUM,
                reasons=reasons,
                factors=factors,
            )

        # 5. Data Export Governance (Row Count & Classification)
        if req_type == ApprovalType.DATA_EXPORT:
            row_count = int(factors.get("row_count", 0))
            data_classification = str(factors.get("data_sensitivity", "INTERNAL")).upper()

            if row_count >= 50000 or (
                row_count >= 10000 and data_classification in ("SENSITIVE", "RESTRICTED")
            ):
                reasons.append(
                    f"Bulk export of {row_count} records with classification {data_classification}"
                )
                return RiskAssessment(
                    risk_level=RiskLevel.CRITICAL,
                    risk_score=self.SCORE_CRITICAL,
                    reasons=reasons,
                    factors=factors,
                )
            if row_count > 1000 or data_classification in (
                "SENSITIVE",
                "RESTRICTED",
                "CONFIDENTIAL",
            ):
                reasons.append(
                    f"Export of {row_count} records with classification {data_classification}"
                )
                return RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    risk_score=self.SCORE_HIGH,
                    reasons=reasons,
                    factors=factors,
                )
            reasons.append("Low volume standard internal data export")
            return RiskAssessment(
                risk_level=RiskLevel.LOW,
                risk_score=self.SCORE_LOW,
                reasons=reasons,
                factors=factors,
            )

        # 6. Report Publication Governance
        if req_type == ApprovalType.REPORT_PUBLICATION:
            classification = str(factors.get("data_sensitivity", "INTERNAL")).upper()
            if classification in ("SENSITIVE", "RESTRICTED"):
                reasons.append(f"Publication of report containing {classification} data")
                return RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    risk_score=self.SCORE_HIGH,
                    reasons=reasons,
                    factors=factors,
                )
            reasons.append("Standard report publication")
            return RiskAssessment(
                risk_level=RiskLevel.LOW,
                risk_score=self.SCORE_LOW,
                reasons=reasons,
                factors=factors,
            )

        # 7. Query Execution & Data Access
        classification = str(factors.get("data_sensitivity", "PUBLIC")).upper()
        row_count = int(factors.get("row_count", 0))
        if classification in ("RESTRICTED", "SENSITIVE"):
            reasons.append(f"Direct access to {classification} corporate data")
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                risk_score=self.SCORE_MEDIUM,
                reasons=reasons,
                factors=factors,
            )
        if row_count > 100000:
            reasons.append("High-volume data query exceeding 100,000 rows")
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                risk_score=self.SCORE_MEDIUM,
                reasons=reasons,
                factors=factors,
            )
        reasons.append("Routine operation under standard policy rules")
        return RiskAssessment(
            risk_level=RiskLevel.LOW,
            risk_score=self.SCORE_LOW,
            reasons=reasons,
            factors=factors,
        )
