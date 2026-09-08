"""Data Classification, sensitivity policy evaluation, and export/LLM governance."""

from dataclasses import dataclass
from typing import Any

from app.compliance.enums import DataClassificationLevel


@dataclass(frozen=True)
class PolicyEvaluationVerdict:
    """Outcome of a sensitivity policy evaluation check."""

    allowed: bool
    verdict: str  # ALLOW, WARN, BLOCK
    reason: str
    requires_approval: bool = False
    details: dict[str, Any] | None = None


class DataClassificationEngine:
    """Evaluates data sensitivity policies across LLM routing, export operations, and agent execution."""

    DEFAULT_POLICIES: dict[str, dict[str, Any]] = {
        DataClassificationLevel.PUBLIC.value: {
            "allowed_providers": ["*"],
            "allow_external_processing": True,
            "allow_export": True,
            "allow_agent_usage": True,
            "allow_embedding": True,
            "retention_days": 730,
        },
        DataClassificationLevel.INTERNAL.value: {
            "allowed_providers": ["*"],
            "allow_external_processing": True,
            "allow_export": True,
            "allow_agent_usage": True,
            "allow_embedding": True,
            "retention_days": 365,
        },
        DataClassificationLevel.CONFIDENTIAL.value: {
            "allowed_providers": ["openai", "anthropic", "azure_openai", "local"],
            "allow_external_processing": True,
            "allow_export": True,
            "allow_agent_usage": True,
            "allow_embedding": True,
            "retention_days": 180,
        },
        DataClassificationLevel.RESTRICTED.value: {
            "allowed_providers": ["local", "azure_openai_private"],
            "allow_external_processing": False,
            "allow_export": False,
            "allow_agent_usage": False,
            "allow_embedding": True,
            "retention_days": 90,
        },
        DataClassificationLevel.SENSITIVE.value: {
            "allowed_providers": ["local"],
            "allow_external_processing": False,
            "allow_export": False,
            "allow_agent_usage": False,
            "allow_embedding": False,
            "retention_days": 30,
        },
    }

    @classmethod
    def get_effective_policy(
        cls,
        classification: str,
        custom_tenant_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve effective policy by blending tenant overrides with baseline defaults."""
        baseline = cls.DEFAULT_POLICIES.get(
            classification, cls.DEFAULT_POLICIES[DataClassificationLevel.INTERNAL.value]
        )
        if custom_tenant_policy:
            return {**baseline, **custom_tenant_policy}
        return baseline

    @classmethod
    def evaluate_llm_routing(
        cls,
        classification: str,
        provider: str,
        custom_tenant_policy: dict[str, Any] | None = None,
    ) -> PolicyEvaluationVerdict:
        """Verify whether an LLM provider is authorized to process data of this classification."""
        policy = cls.get_effective_policy(classification, custom_tenant_policy)
        allowed_providers = policy.get("allowed_providers", [])
        allow_external = policy.get("allow_external_processing", False)

        is_provider_allowed = "*" in allowed_providers or provider.lower() in [
            p.lower() for p in allowed_providers
        ]

        if not allow_external and provider.lower() not in ("local", "internal"):
            return PolicyEvaluationVerdict(
                allowed=False,
                verdict="BLOCK",
                reason=f"External processing prohibited for classification tier '{classification}'.",
                details={"classification": classification, "provider": provider},
            )

        if not is_provider_allowed:
            return PolicyEvaluationVerdict(
                allowed=False,
                verdict="BLOCK",
                reason=f"Provider '{provider}' is not on the approved list for '{classification}'.",
                details={"allowed_providers": allowed_providers, "requested_provider": provider},
            )

        return PolicyEvaluationVerdict(
            allowed=True,
            verdict="ALLOW",
            reason=f"Provider '{provider}' is authorized for '{classification}' data.",
        )

    @classmethod
    def evaluate_export_governance(
        cls,
        classification: str,
        export_format: str,
        custom_tenant_policy: dict[str, Any] | None = None,
    ) -> PolicyEvaluationVerdict:
        """Determine whether data export is allowed, warned, or blocked under governance rules."""
        policy = cls.get_effective_policy(classification, custom_tenant_policy)
        allow_export = policy.get("allow_export", True)

        if not allow_export:
            return PolicyEvaluationVerdict(
                allowed=False,
                verdict="BLOCK",
                reason=f"Data export is strictly prohibited for classification '{classification}'.",
                requires_approval=True,
                details={"classification": classification, "format": export_format},
            )

        if classification in (
            DataClassificationLevel.RESTRICTED.value,
            DataClassificationLevel.SENSITIVE.value,
        ):
            return PolicyEvaluationVerdict(
                allowed=True,
                verdict="WARN",
                reason=f"Exporting '{classification}' data requires administrative audit logging and review.",
                requires_approval=True,
                details={"classification": classification, "format": export_format},
            )

        return PolicyEvaluationVerdict(
            allowed=True,
            verdict="ALLOW",
            reason="Export authorized under standard data handling policy.",
        )

    @classmethod
    def evaluate_agent_governance(
        cls,
        classification: str,
        tool_name: str,
        is_external_tool: bool = False,
        custom_tenant_policy: dict[str, Any] | None = None,
    ) -> PolicyEvaluationVerdict:
        """Validate whether autonomous agent execution is permitted over this data tier."""
        policy = cls.get_effective_policy(classification, custom_tenant_policy)
        allow_agent = policy.get("allow_agent_usage", True)

        if not allow_agent:
            return PolicyEvaluationVerdict(
                allowed=False,
                verdict="BLOCK",
                reason=f"Autonomous agent execution blocked on '{classification}' data.",
                details={"classification": classification, "tool": tool_name},
            )

        if is_external_tool and not policy.get("allow_external_processing", False):
            return PolicyEvaluationVerdict(
                allowed=False,
                verdict="BLOCK",
                reason=f"External tool '{tool_name}' blocked on non-external data tier '{classification}'.",
                details={"tool": tool_name},
            )

        return PolicyEvaluationVerdict(
            allowed=True,
            verdict="ALLOW",
            reason=f"Agent usage approved for '{classification}'.",
        )
