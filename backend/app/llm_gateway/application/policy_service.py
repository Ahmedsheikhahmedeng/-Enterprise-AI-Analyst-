"""Policy enforcement service evaluating tenant governance and data sensitivity rules."""

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm_gateway.domain.enums import DataSensitivity, ModelCapability
from app.llm_gateway.domain.errors import (
    DataSensitivityViolationError,
    TenantPolicyViolationError,
)
from app.llm_gateway.domain.models import ModelDefinition, TenantLLMPolicy
from app.models.llm_gateway import TenantLLMPolicyModel

logger = logging.getLogger(__name__)


class PolicyService:
    """Evaluates tenant-level model policies and data sensitivity boundaries."""

    APPROVED_RESTRICTED_PROVIDERS = {"openai", "deterministic"}

    def validate_tenant_policy(
        self,
        policy: TenantLLMPolicy,
        model: ModelDefinition,
    ) -> None:
        """Enforce tenant allowlists, model capabilities, and residency requirements."""
        # Provider allowlist
        if policy.allowed_providers:
            allowed_provs = {p.lower() for p in policy.allowed_providers}
            if model.provider.lower() not in allowed_provs:
                raise TenantPolicyViolationError(
                    f"Provider '{model.provider}' is not permitted by organization policy."
                )

        # Model allowlist
        if policy.allowed_models:
            allowed_mods = {m.lower() for m in policy.allowed_models}
            if model.model_name.lower() not in allowed_mods:
                raise TenantPolicyViolationError(
                    f"Model '{model.model_name}' is not permitted by organization policy."
                )

        # Required capability allowlist
        if policy.allowed_capabilities:
            missing_caps = policy.allowed_capabilities - model.capabilities
            if missing_caps:
                missing_str = ", ".join(c.value for c in missing_caps)
                raise TenantPolicyViolationError(
                    f"Model '{model.model_name}' lacks tenant-required capabilities: {missing_str}"
                )

    def validate_data_sensitivity(
        self,
        sensitivity: DataSensitivity,
        model: ModelDefinition,
    ) -> None:
        """Enforce data residency and provider sensitivity restrictions."""
        if (
            sensitivity == DataSensitivity.RESTRICTED
            and model.provider.lower() not in self.APPROVED_RESTRICTED_PROVIDERS
        ):
            raise DataSensitivityViolationError(
                f"Provider '{model.provider}' is not certified for RESTRICTED data processing."
            )

    async def get_tenant_policy(
        self,
        session: AsyncSession,
        organization_id: UUID,
    ) -> TenantLLMPolicy:
        """Retrieve tenant LLM policy from database or construct default permissive policy."""
        stmt = select(TenantLLMPolicyModel).where(
            TenantLLMPolicyModel.organization_id == organization_id
        )
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()

        if record is None:
            return TenantLLMPolicy(
                organization_id=organization_id,
                allowed_providers=[],
                allowed_models=[],
                max_tokens_per_request=None,
                max_cost_per_request=None,
                allowed_capabilities=set(),
                data_residency="ANY",
                streaming_allowed=True,
                caching_allowed=True,
            )

        caps = {
            ModelCapability(c)
            for c in record.allowed_capabilities
            if c in ModelCapability._value2member_map_
        }
        return TenantLLMPolicy(
            organization_id=record.organization_id,
            allowed_providers=list(record.allowed_providers),
            allowed_models=list(record.allowed_models),
            max_tokens_per_request=record.max_tokens_per_request,
            max_cost_per_request=Decimal(str(record.max_cost_per_request))
            if record.max_cost_per_request
            else None,
            allowed_capabilities=caps,
            data_residency=record.data_residency,
            streaming_allowed=record.streaming_allowed,
            caching_allowed=record.caching_allowed,
            metadata=record.metadata_ or {},
        )

    async def upsert_tenant_policy(
        self,
        session: AsyncSession,
        policy: TenantLLMPolicy,
    ) -> TenantLLMPolicy:
        """Persist or update tenant LLM policy."""
        stmt = select(TenantLLMPolicyModel).where(
            TenantLLMPolicyModel.organization_id == policy.organization_id
        )
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()

        caps_list = [c.value for c in policy.allowed_capabilities]

        if record is None:
            record = TenantLLMPolicyModel(
                organization_id=policy.organization_id,
                allowed_providers=policy.allowed_providers,
                allowed_models=policy.allowed_models,
                max_tokens_per_request=policy.max_tokens_per_request,
                max_cost_per_request=policy.max_cost_per_request,
                allowed_capabilities=caps_list,
                data_residency=policy.data_residency,
                streaming_allowed=policy.streaming_allowed,
                caching_allowed=policy.caching_allowed,
                metadata_=policy.metadata,
            )
            session.add(record)
        else:
            record.allowed_providers = policy.allowed_providers
            record.allowed_models = policy.allowed_models
            record.max_tokens_per_request = policy.max_tokens_per_request
            record.max_cost_per_request = policy.max_cost_per_request
            record.allowed_capabilities = caps_list
            record.data_residency = policy.data_residency
            record.streaming_allowed = policy.streaming_allowed
            record.caching_allowed = policy.caching_allowed
            record.metadata_ = policy.metadata

        await session.flush()
        return policy
