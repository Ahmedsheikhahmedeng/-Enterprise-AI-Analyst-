"""RAG generation provider routing through Enterprise LLM Gateway."""

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from app.llm_gateway.domain.enums import (
    InputTrustLevel,
    LLMTaskType,
    MessageRole,
    ModelCapability,
)
from app.llm_gateway.domain.models import LLMMessage, LLMRequestPayload
from app.rag.providers.base import RAGLLMProvider, RAGProviderResponse

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class GatewayRAGProvider(RAGLLMProvider):
    """RAG generation adapter executing through central LLMGatewayService."""

    def __init__(
        self,
        gateway_service: Any = None,
        model_name: str = "gpt-4o-mini",
    ) -> None:
        if gateway_service is None:
            from app.llm_gateway.application.gateway_service import get_llm_gateway_service

            self._gateway = get_llm_gateway_service()
        else:
            self._gateway = gateway_service
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "gateway"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> RAGProviderResponse:
        messages = [
            LLMMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
                trust_level=InputTrustLevel.SYSTEM_INSTRUCTION,
            ),
            LLMMessage(
                role=MessageRole.USER,
                content=user_prompt,
                trust_level=InputTrustLevel.USER_INPUT,
            ),
        ]

        payload = LLMRequestPayload(
            messages=messages,
            task_type=LLMTaskType.RAG_ANSWER,
            required_capabilities={ModelCapability.CHAT},
            pinned_model=self._model_name if self._model_name != "auto" else None,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        t_start = time.perf_counter()
        response = await self._gateway.generate(payload)
        latency_ms = (time.perf_counter() - t_start) * 1000

        answer_text = response.content
        evidence_ids: list[str] = []
        confidence = 0.90
        grounded = True

        # Attempt extracting JSON structure if model answered with JSON
        if response.parsed_json:
            answer_text = str(response.parsed_json.get("answer", answer_text))
            evidence_ids = [str(eid) for eid in response.parsed_json.get("evidence_ids", [])]
            confidence = float(response.parsed_json.get("confidence", 0.90))
            grounded = bool(response.parsed_json.get("grounded", True))
        else:
            try:
                parsed = json.loads(response.content)
                if isinstance(parsed, dict):
                    answer_text = str(parsed.get("answer", answer_text))
                    evidence_ids = [str(eid) for eid in parsed.get("evidence_ids", [])]
                    confidence = float(parsed.get("confidence", 0.90))
                    grounded = bool(parsed.get("grounded", True))
            except Exception:
                pass

        return RAGProviderResponse(
            answer=answer_text,
            evidence_ids=evidence_ids,
            confidence=confidence,
            grounded=grounded,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            model=response.model,
            latency_ms=latency_ms,
        )
