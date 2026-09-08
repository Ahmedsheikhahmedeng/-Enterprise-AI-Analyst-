"""Protocol and payload definitions for RAG generation providers."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RAGProviderResponse:
    """Raw structured output produced by a RAG generation provider."""

    answer: str
    evidence_ids: list[str] = field(default_factory=list)
    confidence: float = 0.9
    grounded: bool = True
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    latency_ms: float = 0.0


class RAGLLMProvider(Protocol):
    """Abstract protocol defining interface for LLM answer generation providers."""

    @property
    def provider_name(self) -> str:
        """Identifier of the generation provider."""
        ...

    @property
    def model_name(self) -> str:
        """Active model identifier."""
        ...

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> RAGProviderResponse:
        """Invoke LLM to generate evidence-grounded answer adhering to JSON schema."""
        ...
