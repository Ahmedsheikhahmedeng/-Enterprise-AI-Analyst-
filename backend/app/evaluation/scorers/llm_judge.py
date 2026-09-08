"""LLM-as-a-Judge provider abstraction for semantic qualitative scoring."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMJudgeResult:
    """Structured qualitative evaluation result returned by an LLM Judge."""

    score: float
    label: str  # "excellent", "good", "marginal", "poor"
    reason: str
    metadata: dict[str, Any]


class LLMJudgeProvider(ABC):
    """Abstract interface for LLM Judge qualitative evaluations."""

    @abstractmethod
    async def evaluate(
        self,
        *,
        query: str,
        answer: str,
        evidence_texts: list[str],
    ) -> LLMJudgeResult:
        """Score answer relevance, groundedness, and completeness against evidence."""
        pass


class DeterministicJudgeProvider(LLMJudgeProvider):
    """Offline, deterministic judge used for CI and unit test execution without external API costs."""

    async def evaluate(
        self,
        *,
        query: str,
        answer: str,
        evidence_texts: list[str],
    ) -> LLMJudgeResult:
        if not answer:
            return LLMJudgeResult(
                score=0.0, label="poor", reason="Empty answer provided.", metadata={}
            )

        evidence_str = " ".join(evidence_texts).lower()
        answer_words = [w.lower() for w in answer.split() if len(w) > 3]

        if not answer_words:
            return LLMJudgeResult(
                score=0.5, label="marginal", reason="Short generic answer.", metadata={}
            )

        overlap = sum(1 for w in answer_words if w in evidence_str)
        ratio = overlap / len(answer_words)

        if ratio >= 0.70:
            return LLMJudgeResult(
                score=0.95,
                label="excellent",
                reason="Answer is strongly corroborated by cited evidence context.",
                metadata={"overlap_ratio": ratio},
            )
        elif ratio >= 0.40:
            return LLMJudgeResult(
                score=0.80,
                label="good",
                reason="Answer is moderately supported by evidence.",
                metadata={"overlap_ratio": ratio},
            )
        else:
            return LLMJudgeResult(
                score=0.40,
                label="poor",
                reason="Significant claims lack clear grounding in the provided context.",
                metadata={"overlap_ratio": ratio},
            )


class GatewayJudgeProvider(LLMJudgeProvider):
    """LLM Judge qualitative evaluation provider backed by Enterprise LLM Gateway."""

    def __init__(
        self,
        gateway_service: Any = None,
        model_name: str = "gpt-4o-mini",
        prompt_version: str = "v1",
    ) -> None:
        self._gateway = gateway_service
        self._model_name = model_name
        self.prompt_version = prompt_version
        self._fallback = DeterministicJudgeProvider()

    async def evaluate(
        self,
        *,
        query: str,
        answer: str,
        evidence_texts: list[str],
    ) -> LLMJudgeResult:
        if not answer:
            return LLMJudgeResult(
                score=0.0,
                label="poor",
                reason="Empty answer provided.",
                metadata={
                    "judge_model": self._model_name,
                    "judge_prompt_version": self.prompt_version,
                },
            )

        if self._gateway is None:
            from app.llm_gateway.application.gateway_service import get_llm_gateway_service

            self._gateway = get_llm_gateway_service()

        from app.llm_gateway.domain.enums import (
            InputTrustLevel,
            LLMTaskType,
            MessageRole,
            ModelCapability,
        )
        from app.llm_gateway.domain.models import (
            LLMMessage,
            LLMRequestPayload,
            PromptMetadata,
            StructuredGenerationRequest,
        )

        evidence_str = "\n".join(f"- {e}" for e in evidence_texts)
        messages = [
            LLMMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "You are an impartial evaluation judge assessing AI analyst responses.\n"
                    "Evaluate whether the answer is accurately grounded in the provided evidence context.\n"
                    "Return a JSON object with: 'score' (0.0 to 1.0), 'label' ('excellent', 'good', 'marginal', 'poor'), and 'reason'."
                ),
                trust_level=InputTrustLevel.SYSTEM_INSTRUCTION,
            ),
            LLMMessage(
                role=MessageRole.USER,
                content=f"Query: {query}\n\nEvidence:\n{evidence_str}\n\nAnswer: {answer}",
                trust_level=InputTrustLevel.USER_INPUT,
            ),
        ]

        payload = LLMRequestPayload(
            messages=messages,
            task_type=LLMTaskType.EVALUATION_JUDGE,
            required_capabilities={ModelCapability.CHAT, ModelCapability.STRUCTURED_OUTPUT},
            pinned_model=self._model_name if self._model_name != "auto" else None,
            prompt_metadata=PromptMetadata(
                prompt_name="evaluation_judge",
                prompt_version=self.prompt_version,
            ),
            temperature=0.0,
        )

        structured_req = StructuredGenerationRequest(
            schema={
                "type": "object",
                "properties": {
                    "score": {"type": "number"},
                    "label": {"type": "string", "enum": ["excellent", "good", "marginal", "poor"]},
                    "reason": {"type": "string"},
                },
                "required": ["score", "label", "reason"],
            }
        )

        try:
            resp, _ = await self._gateway.generate_structured(payload, structured_req)
            parsed = resp.parsed_json or {}
            score = float(parsed.get("score", 0.85))
            label = str(parsed.get("label", "good"))
            reason = str(parsed.get("reason", "Corroborated by evidence."))

            return LLMJudgeResult(
                score=score,
                label=label,
                reason=reason,
                metadata={
                    "judge_model": resp.model,
                    "judge_prompt_version": self.prompt_version,
                    "provider": resp.provider,
                },
            )
        except Exception:
            # Fallback gracefully to offline deterministic judge
            res = await self._fallback.evaluate(
                query=query, answer=answer, evidence_texts=evidence_texts
            )
            res.metadata["judge_model"] = f"{self._model_name}-offline-fallback"
            res.metadata["judge_prompt_version"] = self.prompt_version
            return res
