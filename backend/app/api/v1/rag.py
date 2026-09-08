"""REST API endpoints for evidence-grounded RAG answer generation."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.retrieval import get_hybrid_retrieval_service
from app.core.exceptions import (
    AppException,
    BadRequestAppException,
    ValidationAppException,
)
from app.db.postgres import get_db_session
from app.query.service import QueryUnderstandingService
from app.rag.config import get_rag_config
from app.rag.exceptions import (
    RAGConfigurationError,
    RAGError,
    RAGProviderError,
    RAGTenantMismatchError,
    RAGTimeoutError,
)
from app.rag.schemas import (
    CitationResponse,
    EvidenceResponse,
    RAGAnswerRequest,
    RAGAnswerResponse,
    RAGDiagnosticsResponse,
)
from app.rag.service import RAGService
from app.rbac.catalog import PERM_DOCUMENTS_READ
from app.retrieval.hybrid.service import HybridRetrievalService
from app.schemas.common import ErrorResponse
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/rag", tags=["RAG"])


def get_rag_service(
    request: Request,
    hybrid_service: Annotated[HybridRetrievalService, Depends(get_hybrid_retrieval_service)],
) -> RAGService:
    """Resolve or construct singleton RAGService from application state."""
    existing = getattr(request.app.state, "rag_service", None)
    if existing is not None and isinstance(existing, RAGService):
        return existing

    query_service = getattr(request.app.state, "query_understanding_service", None)
    if query_service is not None and not isinstance(query_service, QueryUnderstandingService):
        query_service = None

    service = RAGService(
        hybrid_retrieval_service=hybrid_service,
        query_understanding_service=query_service,
        config=get_rag_config(),
    )
    request.app.state.rag_service = service
    return service


@router.post(
    "/answer",
    response_model=RAGAnswerResponse,
    status_code=status.HTTP_200_OK,
    summary="Evidence-Grounded RAG Answer Generation",
    description=(
        "Executes full RAG pipeline: Query Understanding -> Multi-Query Retrieval -> "
        "Cross-Encoder Reranking -> Evidence Selection -> Grounded Answer Generation "
        "with strict anti-hallucination verification and source citations."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Grounded answer generated successfully"},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Invalid request"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Permission denied"},
        getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422): {
            "model": ErrorResponse,
            "description": "Validation error in parameters",
        },
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse, "description": "Provider error"},
        status.HTTP_504_GATEWAY_TIMEOUT: {"model": ErrorResponse, "description": "RAG timeout"},
    },
)
async def generate_rag_answer(
    request_data: RAGAnswerRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[RAGService, Depends(get_rag_service)],
) -> RAGAnswerResponse:
    """Generate evidence-grounded factual response with citations strictly scoped to tenant."""
    try:
        res = await service.answer(
            query=request_data.query,
            organization_id=tenant.organization_id,
            session=session,
            top_k=request_data.top_k,
            user_id=tenant.user_id,
            conversation_id=request_data.conversation_id,
            analysis_run_id=request_data.analysis_run_id,
        )

        citation_responses = [
            CitationResponse(
                evidence_id=c.evidence_id,
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                page_number=c.page_number,
                source_locator=c.source_locator,
                document_name=c.document_name,
            )
            for c in res.answer.citations
        ]

        evidence_responses = []
        if request_data.include_evidence:
            evidence_responses = [
                EvidenceResponse(
                    evidence_id=ev.evidence_id,
                    document_name=ev.document_name,
                    page_number=ev.page_number,
                    section=ev.section,
                    text=ev.text,
                    rerank_score=ev.rerank_score,
                )
                for ev in res.evidence
            ]

        diag_resp = RAGDiagnosticsResponse(
            retrieved=res.diagnostics.retrieved_count,
            reranked=res.diagnostics.reranked_count,
            evidence_used=res.diagnostics.evidence_count,
            context_tokens=res.diagnostics.context_tokens,
            input_tokens=res.diagnostics.input_tokens,
            output_tokens=res.diagnostics.output_tokens,
            understanding_ms=round(res.diagnostics.understanding_ms, 2),
            retrieval_ms=round(res.diagnostics.retrieval_ms, 2),
            rerank_ms=round(res.diagnostics.rerank_ms, 2),
            llm_latency_ms=round(res.diagnostics.llm_latency_ms, 2),
            total_latency_ms=round(res.diagnostics.total_ms, 2),
            model=res.diagnostics.model,
            provider=res.diagnostics.provider,
            prompt_version=res.diagnostics.prompt_version,
        )

        return RAGAnswerResponse(
            answer=res.answer.answer,
            grounded=res.answer.grounded,
            confidence=res.answer.confidence,
            citations=citation_responses,
            evidence=evidence_responses,
            diagnostics=diag_resp,
        )

    except RAGTenantMismatchError as exc:
        raise BadRequestAppException(message=str(exc)) from exc
    except RAGConfigurationError as exc:
        raise BadRequestAppException(message=str(exc)) from exc
    except RAGTimeoutError as exc:
        raise AppException(
            message=f"RAG generation timed out: {exc}",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            code="RAG_TIMEOUT",
        ) from exc
    except RAGProviderError as exc:
        raise AppException(
            message=f"RAG provider error: {exc}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="RAG_PROVIDER_ERROR",
        ) from exc
    except RAGError as exc:
        raise AppException(
            message=f"RAG error: {exc}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="RAG_ERROR",
        ) from exc
    except Exception as exc:
        raise ValidationAppException(message=str(exc)) from exc
