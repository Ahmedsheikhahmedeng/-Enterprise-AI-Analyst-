"""Final grounded generation service executing synthesis through Enterprise LLM Gateway."""

import logging

from app.llm_gateway.application.gateway_service import LLMGatewayService
from app.llm_gateway.domain.enums import InputTrustLevel, LLMTaskType, MessageRole
from app.llm_gateway.domain.models import LLMMessage, LLMRequestPayload
from app.response_orchestration.domain.enums import ResponseStyle
from app.response_orchestration.domain.models import (
    EvidenceBundle,
    EvidenceConflict,
    UnifiedReasoningPlan,
)
from app.tenancy.context import TenantContext

logger = logging.getLogger(__name__)


class ResponseService:
    """Constructs secured grounded generation prompts and invokes the Enterprise LLM Gateway."""

    def __init__(self, llm_gateway: LLMGatewayService) -> None:
        self.llm_gateway = llm_gateway

    def _build_system_prompt(self, style: ResponseStyle) -> str:
        """Construct immutable system instructions enforcing strict evidence grounding."""
        style_instruction = "Provide a comprehensive, well-structured response."
        if style == ResponseStyle.CONCISE:
            style_instruction = (
                "Be direct, concise, and focused on core numerical and factual takeaways."
            )
        elif style == ResponseStyle.EXECUTIVE:
            style_instruction = "Format as an Executive Briefing: highlight headline metrics, strategic insights, and caveats."
        elif style == ResponseStyle.DETAILED:
            style_instruction = "Provide detailed analysis including methodology, definitions, and supporting evidence."

        return (
            "You are the Enterprise AI Decision Orchestrator. Answer questions STRICTLY and ONLY "
            "from the supplied factual evidence snippets. Every statement MUST be attributed with its exact "
            "citation tag (e.g. [S1], [D1], [G1], [M1]). Do NOT invent facts or hallucinate citations. "
            "Explicitly disclose any noted discrepancies or partial data branch failures.\n"
            f"Tone and Formatting: {style_instruction}"
        )

    def _format_evidence_context(
        self,
        evidence_bundle: EvidenceBundle,
        conflicts: list[EvidenceConflict],
    ) -> str:
        """Serialize evidence bundle into structured prompt context."""
        parts = ["=== VERIFIED ENTERPRISE EVIDENCE ==="]
        for it in evidence_bundle.items:
            tag = it.citation_id or "[EV]"
            parts.append(f"{tag} ({it.source_type.value.upper()}) {it.content}")

        if conflicts:
            parts.append("\n=== DETECTED DATA CONFLICTS ===")
            for c in conflicts:
                parts.append(
                    f"- Discrepancy on '{c.field}': {c.source_a} reports {c.value_a} vs {c.source_b} reports {c.value_b}"
                )

        return "\n".join(parts)

    async def generate_grounded_response(
        self,
        query: str,
        plan: UnifiedReasoningPlan,
        evidence_bundle: EvidenceBundle,
        conflicts: list[EvidenceConflict],
        style: ResponseStyle,
        tenant_context: TenantContext | None = None,
        is_partial: bool = False,
    ) -> tuple[str, str | None]:
        """Synthesize final response via LLM Gateway."""
        if not evidence_bundle.items:
            return (
                "No relevant structured data, approved metrics, or document evidence found to answer this query.",
                None,
            )

        system_instruction = self._build_system_prompt(style)
        evidence_context = self._format_evidence_context(evidence_bundle, conflicts)

        user_content = f"User Question: {query}\n\n{evidence_context}\n\n"
        if is_partial:
            user_content += (
                "Note: Analysis is partial due to an execution failure in one data branch.\n"
            )

        messages = [
            LLMMessage(
                role=MessageRole.SYSTEM,
                content=system_instruction,
                trust_level=InputTrustLevel.SYSTEM_INSTRUCTION,
            ),
            LLMMessage(
                role=MessageRole.USER,
                content=user_content,
                trust_level=InputTrustLevel.USER_INPUT,
            ),
        ]

        payload = LLMRequestPayload(
            messages=messages,
            task_type=LLMTaskType.FINAL_RESPONSE_GENERATION,
            temperature=0.0,  # Zero temperature for factual grounded generation
            max_tokens=2048,
        )

        try:
            resp = await self.llm_gateway.generate(payload, tenant_context=tenant_context)
            return resp.content, resp.model
        except Exception as exc:
            logger.warning(
                "LLM Gateway synthesis failed, falling back to deterministic synthesis: %s", exc
            )
            # Deterministic synthesis fallback
            fallback_parts = []
            for it in evidence_bundle.items[:3]:
                fallback_parts.append(f"{it.content} [{it.citation_id or 'E'}]")
            return " ".join(fallback_parts), "deterministic-fallback"
