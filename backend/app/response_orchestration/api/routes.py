"""REST API routes for Enterprise AI Response Orchestration."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.llm_gateway.application.gateway_service import LLMGatewayService
from app.rag.service import RAGService
from app.rbac.catalog import (
    PERM_ORCHESTRATION_EXECUTE,
    PERM_ORCHESTRATION_READ,
)
from app.response_orchestration.api.schemas import (
    CitationItemSchema,
    ConflictItemSchema,
    EnterpriseAskRequest,
    EnterpriseAskResponse,
    OrchestrationPreviewResponse,
)
from app.response_orchestration.application.orchestration_service import (
    ResponseOrchestrationService,
)
from app.response_orchestration.domain.models import EnterpriseQueryRequest
from app.response_orchestration.infrastructure.repository import OrchestrationRepository
from app.sql_agent.service import SQLAgentService
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

ask_router = APIRouter(prefix="/ask", tags=["Response Orchestration"])


def get_orchestration_service(request: Request) -> ResponseOrchestrationService:
    """Resolve or construct singleton ResponseOrchestrationService from app state."""
    existing = getattr(request.app.state, "response_orchestration_service", None)
    if existing is not None and isinstance(existing, ResponseOrchestrationService):
        return existing

    sql_svc = getattr(request.app.state, "sql_agent_service", None)
    if sql_svc is None:
        sql_svc = SQLAgentService()
        request.app.state.sql_agent_service = sql_svc

    rag_svc = getattr(request.app.state, "rag_service", None)
    if rag_svc is None and getattr(request.app.state, "hybrid_retrieval_service", None):
        from app.rag.config import get_rag_config

        rag_svc = RAGService(
            hybrid_retrieval_service=request.app.state.hybrid_retrieval_service,
            config=get_rag_config(),
        )
        request.app.state.rag_service = rag_svc

    llm_gateway = getattr(request.app.state, "llm_gateway_service", None)
    if llm_gateway is None:
        llm_gateway = LLMGatewayService()
        request.app.state.llm_gateway_service = llm_gateway

    service = ResponseOrchestrationService(
        sql_service=sql_svc,
        rag_service=rag_svc,
        llm_gateway=llm_gateway,
    )
    request.app.state.response_orchestration_service = service
    return service


@ask_router.post(
    "",
    response_model=EnterpriseAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Canonical enterprise query and decision orchestration",
)
async def ask_enterprise(
    request_payload: EnterpriseAskRequest,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_EXECUTE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ResponseOrchestrationService, Depends(get_orchestration_service)],
) -> EnterpriseAskResponse:
    """Execute canonical end-to-end multi-modal query across SQL, RAG, Semantics, and Knowledge Graph."""
    domain_req = EnterpriseQueryRequest(
        question=request_payload.question,
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        conversation_id=request_payload.conversation_id,
        mode=request_payload.mode,
        response_style=request_payload.response_style,
        target_dataset_id=request_payload.target_dataset_id,
        enable_clarification=request_payload.enable_clarification,
    )

    result = await service.ask(
        request=domain_req,
        session=session,
        tenant_context=tenant_context,
    )

    return EnterpriseAskResponse(
        execution_id=result.execution_id,
        request_id=result.request_id,
        trace_id=result.trace_id,
        answer=result.answer,
        status=result.status,
        decision=result.decision,
        confidence_score=result.confidence_score,
        evidence_coverage=result.evidence_coverage,
        citations=[
            CitationItemSchema(
                citation_id=c.citation_id,
                source_type=c.source_type.value,
                source_id=c.source_id,
                title=c.title,
                snippet=c.snippet,
                trust_level=c.trust_level,
            )
            for c in result.citations
        ],
        conflicts=[
            ConflictItemSchema(
                conflict_id=cf.conflict_id,
                field=cf.field,
                source_a=cf.source_a,
                value_a=cf.value_a,
                source_b=cf.source_b,
                value_b=cf.value_b,
                severity=cf.severity,
                description=cf.description,
                resolved_value=cf.resolved_value,
            )
            for cf in result.conflicts
        ],
        warnings=result.warnings,
        clarification_prompt=result.clarification_prompt,
        provenance=result.provenance,
        diagnostics=result.diagnostics,
    )


@ask_router.post(
    "/preview",
    response_model=OrchestrationPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview reasoning strategy and semantic matches without full synthesis",
)
async def preview_query(
    request_payload: EnterpriseAskRequest,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_EXECUTE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ResponseOrchestrationService, Depends(get_orchestration_service)],
) -> OrchestrationPreviewResponse:
    """Preview reasoning plan and metrics resolution."""
    plan = await service._plan_reasoning(
        question=request_payload.question,
        organization_id=tenant_context.organization_id,
        mode=request_payload.mode,
        session=session,
        target_dataset_id=request_payload.target_dataset_id,
    )
    return OrchestrationPreviewResponse(
        strategy=plan.execution_strategy.value,
        resolved_metrics=plan.resolved_metrics,
        resolved_dimensions=plan.resolved_dimensions,
        requires_clarification=plan.requires_clarification,
        clarification_options=plan.clarification_options,
    )


@ask_router.get(
    "/{execution_id}",
    response_model=EnterpriseAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve orchestration execution details by ID",
)
async def get_execution_record(
    execution_id: uuid.UUID,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EnterpriseAskResponse:
    """Retrieve recorded orchestration status, answer, and telemetry enforcing tenant boundary."""
    repo = OrchestrationRepository(session)
    record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration execution not found."
        )

    from app.response_orchestration.domain.enums import DecisionType, OrchestrationStatus

    return EnterpriseAskResponse(
        execution_id=record.id,
        request_id=record.id,
        trace_id=str(record.id),
        answer=record.answer or "",
        status=OrchestrationStatus(record.status),
        decision=DecisionType(record.decision),
        confidence_score=float(record.confidence_score),
        evidence_coverage=float(record.evidence_coverage),
        citations=[CitationItemSchema(**c) for c in (record.citations or [])],
        conflicts=[ConflictItemSchema(**cf) for cf in (record.conflicts or [])],
        warnings=record.warnings or [],
        clarification_prompt=record.clarification_prompt,
        provenance=record.provenance or {},
        diagnostics=record.diagnostics or {},
    )
