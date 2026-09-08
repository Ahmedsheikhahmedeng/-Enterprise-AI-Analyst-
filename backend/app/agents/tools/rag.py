"""Typed adapter tool wrapping RAGService."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import RAGRetrieveInput
from app.rag.service import RAGService
from app.rbac.catalog import PERM_AI_CHAT


class RAGTool:
    """Tool executing grounded semantic retrieval and document analysis."""

    name: str = "rag.retrieve"
    version: str = "v1.0"
    description: str = "Retrieves semantic document context and generates grounded answers."
    input_schema: type[BaseModel] = RAGRetrieveInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_AI_CHAT
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    def __init__(self, rag_service: RAGService | None = None) -> None:
        self.rag_service = rag_service

    async def validate(self, tool_input: dict[str, Any]) -> RAGRetrieveInput:
        try:
            return RAGRetrieveInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, RAGRetrieveInput)
            else RAGRetrieveInput.model_validate(validated_input)
        )
        return {
            "action": "execute_rag_retrieval",
            "query": inp.query,
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, RAGRetrieveInput)
            else RAGRetrieveInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()

        if self.rag_service is None:
            raise RuntimeError("RAG service is not configured or unavailable.")
        rag_svc = self.rag_service

        result = await rag_svc.answer(
            query=inp.query,
            organization_id=context.organization_id,
            session=context.db_session,
            top_k=inp.top_k,
            user_id=context.user_id,
        )

        duration_ms = (time.perf_counter() - t_start) * 1000

        evidence_items = []
        for ev in result.evidence:
            evidence_items.append(
                {
                    "evidence_id": ev.evidence_id,
                    "source_type": "rag",
                    "content": ev.text,
                    "metadata": {
                        "document_id": str(ev.document_id),
                        "document_name": ev.document_name,
                        "source_locator": ev.source_locator,
                    },
                }
            )

        citations = [c.evidence_id for c in result.answer.citations]
        total_tokens = result.diagnostics.input_tokens + result.diagnostics.output_tokens

        return ToolOutput(
            success=result.answer.grounded,
            data={
                "answer": result.answer.answer,
                "citations": citations,
                "grounded": result.answer.grounded,
            },
            evidence_items=evidence_items,
            tokens_used=total_tokens or 100,
            cost_usd=result.diagnostics.cost_usd or 0.0015,
            duration_ms=duration_ms,
        )
