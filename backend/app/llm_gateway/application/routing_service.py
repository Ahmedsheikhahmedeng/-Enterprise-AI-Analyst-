"""Model Routing Service delivering deterministic, capability-aware model selection."""

import logging

from app.llm_gateway.domain.enums import (
    DataSensitivity,
    LLMTaskType,
    ModelCapability,
    ModelStatus,
    RoutingStrategy,
)
from app.llm_gateway.domain.errors import (
    CapabilityMismatchError,
    NoHealthyProviderError,
)
from app.llm_gateway.domain.models import (
    LLMRequestPayload,
    ModelDefinition,
    TenantLLMPolicy,
)
from app.llm_gateway.infrastructure.registry import ModelRegistry

logger = logging.getLogger(__name__)


class RoutingService:
    """Selects candidate models based on task requirements, routing strategy, and tenant governance."""

    def __init__(self, model_registry: ModelRegistry) -> None:
        self.registry = model_registry

    def _infer_task_capabilities(self, task_type: LLMTaskType) -> set[ModelCapability]:
        """Derive standard required capabilities based on task classification."""
        caps = {ModelCapability.CHAT}
        if task_type in (LLMTaskType.SQL_GENERATION, LLMTaskType.EVALUATION_JUDGE):
            caps.add(ModelCapability.STRUCTURED_OUTPUT)
        return caps

    def resolve_routing_plan(
        self,
        payload: LLMRequestPayload,
        policy: TenantLLMPolicy | None = None,
        open_circuit_providers: set[str] | None = None,
    ) -> list[ModelDefinition]:
        """Produce an ordered list of candidate models for invocation and failover."""
        open_circuits = {p.lower() for p in (open_circuit_providers or set())}
        required_caps = set(payload.required_capabilities) | self._infer_task_capabilities(
            payload.task_type
        )

        # 1. Pinned model handling
        if payload.pinned_model:
            candidate_providers = (
                [payload.pinned_provider]
                if payload.pinned_provider
                else ["openai", "deterministic"]
            )
            for prov in candidate_providers:
                try:
                    pinned = self.registry.get_model(prov, payload.pinned_model)
                    if pinned.status == ModelStatus.ACTIVE and pinned.is_approved:
                        missing = required_caps - pinned.capabilities
                        if missing:
                            raise CapabilityMismatchError(
                                f"Pinned model '{payload.pinned_model}' lacks requested capabilities."
                            )
                        candidates = [pinned]
                        try:
                            mock_model = self.registry.get_model("deterministic", "mock-model")
                            if mock_model not in candidates:
                                candidates.append(mock_model)
                        except Exception:
                            pass
                        return candidates
                except CapabilityMismatchError:
                    raise
                except Exception:
                    continue

        # 2. General Candidate Discovery
        all_models = self.registry.list_models(status=ModelStatus.ACTIVE, approved_only=True)
        valid_candidates: list[ModelDefinition] = []

        for model in all_models:
            # Check circuit breaker
            if model.provider.lower() in open_circuits:
                continue

            # Check capabilities
            if not required_caps.issubset(model.capabilities):
                continue

            # Check Tenant Policy
            if (
                policy
                and policy.allowed_providers
                and model.provider.lower() not in {p.lower() for p in policy.allowed_providers}
            ):
                continue
            if (
                policy
                and policy.allowed_models
                and model.model_name.lower() not in {m.lower() for m in policy.allowed_models}
            ):
                continue

            # Check Data Sensitivity
            if (
                payload.data_sensitivity == DataSensitivity.RESTRICTED
                and model.provider.lower() not in ("openai", "deterministic")
            ):
                continue

            valid_candidates.append(model)

        if not valid_candidates:
            # Ensure deterministic fallback model is always available if permitted
            try:
                mock = self.registry.get_model("deterministic", "mock-model")
                if "deterministic" not in open_circuits:
                    valid_candidates.append(mock)
            except Exception:
                pass

        if not valid_candidates:
            raise NoHealthyProviderError("No healthy or policy-compliant models found for request.")

        # 3. Apply Routing Strategy Sorting
        strategy = payload.routing_strategy
        if strategy == RoutingStrategy.QUALITY_FIRST:
            valid_candidates.sort(
                key=lambda m: (
                    1 if m.provider != "deterministic" else 0,
                    m.priority,
                    m.pricing.input_price_per_1k,
                ),
                reverse=True,
            )
        elif strategy == RoutingStrategy.COST_FIRST:
            valid_candidates.sort(
                key=lambda m: (
                    m.pricing.input_price_per_1k + m.pricing.output_price_per_1k,
                    -m.priority,
                )
            )
        elif strategy == RoutingStrategy.LATENCY_FIRST:
            valid_candidates.sort(
                key=lambda m: (
                    1 if "mini" in m.model_name or "mock" in m.model_name else 0,
                    m.priority,
                ),
                reverse=True,
            )
        else:  # BALANCED
            valid_candidates.sort(
                key=lambda m: (
                    m.priority,
                    -(m.pricing.input_price_per_1k + m.pricing.output_price_per_1k),
                ),
                reverse=True,
            )

        # Always append deterministic fallback at the tail if not already present
        try:
            mock = self.registry.get_model("deterministic", "mock-model")
            if mock not in valid_candidates:
                valid_candidates.append(mock)
        except Exception:
            pass

        return valid_candidates
