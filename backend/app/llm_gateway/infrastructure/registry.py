"""Provider and Model Registries for Enterprise LLM Gateway."""

from collections.abc import Callable
from decimal import Decimal

from app.llm_gateway.domain.enums import ModelCapability, ModelStatus
from app.llm_gateway.domain.errors import ModelNotFoundError, ProviderNotFoundError
from app.llm_gateway.domain.models import ModelDefinition, ModelPricing
from app.llm_gateway.domain.protocols import LLMProvider


class ProviderRegistry:
    """Central registry of approved and instantiated LLM provider adapters."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], LLMProvider]] = {}
        self._instances: dict[str, LLMProvider] = {}

    def register(self, provider_name: str, factory: Callable[[], LLMProvider]) -> None:
        """Register a provider factory by name."""
        self._factories[provider_name.lower()] = factory

    def get_provider(self, provider_name: str) -> LLMProvider:
        """Obtain or instantiate provider adapter singleton."""
        norm_name = provider_name.lower()
        if norm_name in self._instances:
            return self._instances[norm_name]
        if norm_name in self._factories:
            instance = self._factories[norm_name]()
            self._instances[norm_name] = instance
            return instance
        raise ProviderNotFoundError(f"LLM Provider '{provider_name}' is not registered.")

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return sorted(self._factories.keys())


class ModelRegistry:
    """Catalog of enterprise-governed models with pricing, capabilities, and status."""

    def __init__(self) -> None:
        self._models: dict[str, ModelDefinition] = {}
        self._seed_default_models()

    def _seed_default_models(self) -> None:
        """Populate initial supported model catalog."""
        # 1. Deterministic / Offline mock model for testing and CI
        self.register_model(
            ModelDefinition(
                provider="deterministic",
                model_name="mock-model",
                model_version="1.0",
                status=ModelStatus.ACTIVE,
                is_approved=True,
                capabilities={
                    ModelCapability.CHAT,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.TOOL_CALLING,
                    ModelCapability.JSON_MODE,
                    ModelCapability.STREAMING,
                    ModelCapability.LONG_CONTEXT,
                },
                pricing=ModelPricing(
                    input_price_per_1k=Decimal("0.0"),
                    output_price_per_1k=Decimal("0.0"),
                ),
                context_window=128000,
                max_output_tokens=4096,
                priority=10,
            )
        )

        # 2. OpenAI Flagship: gpt-4o
        self.register_model(
            ModelDefinition(
                provider="openai",
                model_name="gpt-4o",
                model_version="latest",
                status=ModelStatus.ACTIVE,
                is_approved=True,
                capabilities={
                    ModelCapability.CHAT,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.TOOL_CALLING,
                    ModelCapability.JSON_MODE,
                    ModelCapability.STREAMING,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.VISION,
                },
                pricing=ModelPricing(
                    input_price_per_1k=Decimal("0.005"),
                    output_price_per_1k=Decimal("0.015"),
                ),
                context_window=128000,
                max_output_tokens=4096,
                priority=100,
            )
        )

        # 3. OpenAI Cost-Optimized: gpt-4o-mini
        self.register_model(
            ModelDefinition(
                provider="openai",
                model_name="gpt-4o-mini",
                model_version="latest",
                status=ModelStatus.ACTIVE,
                is_approved=True,
                capabilities={
                    ModelCapability.CHAT,
                    ModelCapability.STRUCTURED_OUTPUT,
                    ModelCapability.TOOL_CALLING,
                    ModelCapability.JSON_MODE,
                    ModelCapability.STREAMING,
                    ModelCapability.LONG_CONTEXT,
                },
                pricing=ModelPricing(
                    input_price_per_1k=Decimal("0.00015"),
                    output_price_per_1k=Decimal("0.0006"),
                ),
                context_window=128000,
                max_output_tokens=4096,
                priority=50,
            )
        )

        # 4. OpenAI Legacy: gpt-3.5-turbo
        self.register_model(
            ModelDefinition(
                provider="openai",
                model_name="gpt-3.5-turbo",
                model_version="latest",
                status=ModelStatus.ACTIVE,
                is_approved=True,
                capabilities={
                    ModelCapability.CHAT,
                    ModelCapability.JSON_MODE,
                    ModelCapability.STREAMING,
                },
                pricing=ModelPricing(
                    input_price_per_1k=Decimal("0.0005"),
                    output_price_per_1k=Decimal("0.0015"),
                ),
                context_window=16385,
                max_output_tokens=4096,
                priority=20,
            )
        )

    def register_model(self, model: ModelDefinition) -> None:
        """Register or update a model definition."""
        key = f"{model.provider.lower()}:{model.model_name.lower()}"
        self._models[key] = model

    def get_model(self, provider: str, model_name: str) -> ModelDefinition:
        """Retrieve model definition by provider and model name."""
        key = f"{provider.lower()}:{model_name.lower()}"
        if key not in self._models:
            raise ModelNotFoundError(
                f"Model '{model_name}' for provider '{provider}' not found in registry."
            )
        return self._models[key]

    def list_models(
        self,
        provider: str | None = None,
        status: ModelStatus | None = None,
        approved_only: bool = True,
    ) -> list[ModelDefinition]:
        """List registered models satisfying optional filter criteria."""
        results: list[ModelDefinition] = []
        for model in self._models.values():
            if provider and model.provider.lower() != provider.lower():
                continue
            if status and model.status != status:
                continue
            if approved_only and not model.is_approved:
                continue
            results.append(model)
        return sorted(results, key=lambda m: m.priority, reverse=True)

    def set_model_status(
        self, provider: str, model_name: str, status: ModelStatus
    ) -> ModelDefinition:
        """Update model operational status (e.g. DEPRECATED or DISABLED)."""
        model = self.get_model(provider, model_name)
        model.status = status
        return model

    def set_model_approval(self, provider: str, model_name: str, approved: bool) -> ModelDefinition:
        """Approve or unapprove model."""
        model = self.get_model(provider, model_name)
        model.is_approved = approved
        return model
