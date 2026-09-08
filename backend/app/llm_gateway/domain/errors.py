"""Domain exceptions for Enterprise LLM Gateway."""

from typing import Any


class LLMError(Exception):
    """Base exception for all LLM Gateway errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LLMTimeoutError(LLMError):
    """Raised when request execution times out against an LLM provider."""


class LLMRateLimitError(LLMError):
    """Raised when an LLM provider rejects requests due to rate limits (HTTP 429)."""


class LLMProviderError(LLMError):
    """Raised when an upstream LLM provider fails with 5xx or connection error."""


class LLMCircuitOpenError(LLMError):
    """Raised when a provider's circuit breaker is in OPEN state."""


class CapabilityMismatchError(LLMError):
    """Raised when candidate models lack requested capabilities."""


class LLMBudgetError(LLMError):
    """Base exception for token and cost budget rejections."""


class TokenBudgetExceededError(LLMBudgetError):
    """Raised when request tokens exceed tenant or agent budget caps."""


class CostBudgetExceededError(LLMBudgetError):
    """Raised when pre-flight or post-execution cost exceeds cost limits."""


class LLMPolicyViolationError(LLMError):
    """Base exception for policy and governance rejections."""


class TenantPolicyViolationError(LLMPolicyViolationError):
    """Raised when request violates tenant model or provider allowlists."""


class DataSensitivityViolationError(LLMPolicyViolationError):
    """Raised when restricted or sensitive data cannot be sent to candidate providers."""


class SecurityViolationError(LLMError):
    """Security rejections that must halt immediately without fallback."""


class PromptInjectionBoundaryError(SecurityViolationError):
    """Raised when untrusted user or document input attempts to elevate to system role."""


class StructuredOutputValidationError(LLMError):
    """Raised when structured JSON output fails schema or Pydantic validation."""


class SchemaSafetyViolationError(StructuredOutputValidationError):
    """Raised when structured output schema exceeds safe nesting or size bounds."""


class ProviderNotFoundError(LLMError):
    """Raised when a requested provider is not registered."""


class ModelNotFoundError(LLMError):
    """Raised when a requested model is not found in the registry."""


class NoHealthyProviderError(LLMError):
    """Raised when all candidate and fallback providers are unhealthy or circuit-broken."""
