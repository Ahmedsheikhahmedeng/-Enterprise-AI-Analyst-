"""Governance policy engine and tenant versioning service."""

import logging
import uuid
from typing import Any

from app.governance.domain.enums import ApprovalType, RiskLevel
from app.governance.domain.errors import PolicyNotFoundError, PolicyViolationError
from app.governance.domain.models import ApprovalRequirement, GovernancePolicy, RiskAssessment
from app.governance.infrastructure.cache import GovernanceCache, get_governance_cache
from app.governance.infrastructure.repository import GovernanceRepository

logger = logging.getLogger(__name__)

# Default Enterprise Baseline Policy
DEFAULT_GOVERNANCE_RULES: dict[str, Any] = {
    "risk_thresholds": {
        "LOW": {
            "requires_human_approval": False,
            "minimum_approvers": 0,
            "allowed_roles": ["Viewer", "Analyst", "Admin"],
            "timeout_minutes": 1440,
            "disallow_self_approval": False,
        },
        "MEDIUM": {
            "requires_human_approval": True,
            "minimum_approvers": 1,
            "allowed_roles": ["Analyst", "Admin"],
            "timeout_minutes": 1440,
            "disallow_self_approval": True,
        },
        "HIGH": {
            "requires_human_approval": True,
            "minimum_approvers": 1,
            "allowed_roles": ["Admin"],
            "timeout_minutes": 1440,
            "disallow_self_approval": True,
        },
        "CRITICAL": {
            "requires_human_approval": True,
            "minimum_approvers": 2,
            "allowed_roles": ["Admin"],
            "timeout_minutes": 720,
            "disallow_self_approval": True,
        },
    },
    "custom_overrides": {},
}


class PolicyService:
    """Manages versioned tenant policies and determines approval requirements."""

    def __init__(
        self,
        repository: GovernanceRepository,
        cache: GovernanceCache | None = None,
    ) -> None:
        self.repo = repository
        self.cache = cache or get_governance_cache()

    async def get_active_policy(self, organization_id: uuid.UUID) -> GovernancePolicy:
        """Fetch the active governance policy for an organization or initialize default v1."""
        record = await self.repo.get_active_policy(organization_id)
        if not record:
            # Auto-initialize baseline v1 policy for tenant
            record = await self.repo.create_policy(
                organization_id=organization_id,
                rules=DEFAULT_GOVERNANCE_RULES,
                policy_version=1,
                status="ACTIVE",
            )
        return GovernancePolicy(
            id=record.id,
            organization_id=record.organization_id,
            policy_version=record.policy_version,
            rules=record.rules,
            status=record.status,
            created_by=record.created_by,
            approved_by=record.approved_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def get_policy_by_version(
        self, organization_id: uuid.UUID, version: int
    ) -> GovernancePolicy:
        """Fetch policy at a specific immutable historical version."""
        record = await self.repo.get_policy_by_version(organization_id, version)
        if not record:
            raise PolicyNotFoundError(
                f"Policy version {version} not found for organization {organization_id}"
            )
        return GovernancePolicy(
            id=record.id,
            organization_id=record.organization_id,
            policy_version=record.policy_version,
            rules=record.rules,
            status=record.status,
            created_by=record.created_by,
            approved_by=record.approved_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def update_policy(
        self,
        organization_id: uuid.UUID,
        new_rules: dict[str, Any],
        creator_id: uuid.UUID,
        approver_id: uuid.UUID | None = None,
    ) -> GovernancePolicy:
        """Create a new policy version increment while enforcing anti-downgrade constraints."""
        current_policy = await self.get_active_policy(organization_id)

        # Anti-downgrade protection: Prevent eliminating approvals on CRITICAL/HIGH tiers
        thresholds = new_rules.get("risk_thresholds", {})
        critical_cfg = thresholds.get("CRITICAL", {})
        if critical_cfg and critical_cfg.get("requires_human_approval") is False:
            raise PolicyViolationError(
                "Anti-downgrade violation: CRITICAL tier requires human approval"
            )
        if critical_cfg and critical_cfg.get("minimum_approvers", 2) < 2:
            raise PolicyViolationError(
                "Anti-downgrade violation: CRITICAL tier requires at least 2 approvers"
            )

        high_cfg = thresholds.get("HIGH", {})
        if high_cfg and high_cfg.get("requires_human_approval") is False:
            raise PolicyViolationError(
                "Anti-downgrade violation: HIGH tier requires human approval"
            )

        next_version = current_policy.policy_version + 1
        new_record = await self.repo.create_policy(
            organization_id=organization_id,
            rules=new_rules,
            policy_version=next_version,
            status="ACTIVE",
            created_by=creator_id,
            approved_by=approver_id,
        )
        await self.cache.invalidate_policy(organization_id)

        return GovernancePolicy(
            id=new_record.id,
            organization_id=new_record.organization_id,
            policy_version=new_record.policy_version,
            rules=new_record.rules,
            status=new_record.status,
            created_by=new_record.created_by,
            approved_by=new_record.approved_by,
            created_at=new_record.created_at,
            updated_at=new_record.updated_at,
        )

    def evaluate_requirement(
        self,
        policy: GovernancePolicy,
        risk: RiskAssessment,
        request_type: ApprovalType,
    ) -> ApprovalRequirement:
        """Determine approval requirement given assessed risk and tenant policy."""
        rules = policy.rules or DEFAULT_GOVERNANCE_RULES
        thresholds = rules.get("risk_thresholds", DEFAULT_GOVERNANCE_RULES["risk_thresholds"])
        tier_cfg = thresholds.get(risk.risk_level.value, thresholds["LOW"])

        required = bool(tier_cfg.get("requires_human_approval", False))
        min_approvers = int(tier_cfg.get("minimum_approvers", 1 if required else 0))
        allowed_roles = list(tier_cfg.get("allowed_roles", ["Admin"]))
        timeout = int(tier_cfg.get("timeout_minutes", 1440))
        disallow_self = bool(tier_cfg.get("disallow_self_approval", True))

        # Absolute safety bound: CRITICAL always mandates 2 approvers and disallows self-approval
        if risk.risk_level == RiskLevel.CRITICAL:
            required = True
            min_approvers = max(2, min_approvers)
            disallow_self = True
            allowed_roles = ["Admin"]

        return ApprovalRequirement(
            required=required,
            minimum_approvers=min_approvers,
            required_roles=allowed_roles,
            required_permission="governance.approve",
            timeout_minutes=timeout,
            disallow_self_approval=disallow_self,
        )
