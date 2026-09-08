"""REST API endpoints for query understanding and semantic planning."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.exceptions import (
    AppException,
    BadRequestAppException,
    ValidationAppException,
)
from app.query.config import get_query_understanding_config
from app.query.exceptions import (
    QueryProviderError,
    QuerySafetyError,
    QueryTimeoutError,
    QueryUnderstandingError,
    QueryValidationError,
)
from app.query.schemas import (
    ExtractedEntityResponse,
    QueryAnalysisRequest,
    QueryAnalysisResponse,
    QueryDiagnosticsResponse,
    SearchPlanResponse,
)
from app.query.service import QueryUnderstandingService
from app.rbac.catalog import PERM_DOCUMENTS_READ
from app.schemas.common import ErrorResponse
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/query", tags=["Query Understanding"])


def get_query_understanding_service(request: Request) -> QueryUnderstandingService:
    """Resolve singleton QueryUnderstandingService from application state or create default."""
    existing = getattr(request.app.state, "query_understanding_service", None)
    if existing is not None and isinstance(existing, QueryUnderstandingService):
        return existing
    return QueryUnderstandingService(config=get_query_understanding_config())


@router.post(
    "/analyze",
    response_model=QueryAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze query, extract entities, and construct SearchPlan",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid query payload",
        },
        getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422): {
            "model": ErrorResponse,
            "description": "Validation error",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Analysis failure",
        },
    },
)
async def analyze_query(
    request_data: QueryAnalysisRequest,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))
    ],
    service: Annotated[QueryUnderstandingService, Depends(get_query_understanding_service)],
) -> QueryAnalysisResponse:
    """Analyze query and return structured search plan for multi-query execution."""
    try:
        plan = await service.analyze_and_plan(
            query=request_data.query,
            organization_id=tenant_context.organization_id,
            enable_rewrite=request_data.enable_rewrite,
            enable_expansion=request_data.enable_expansion,
            enable_decomposition=request_data.enable_decomposition,
            max_alternatives=request_data.max_alternatives,
            max_subqueries=request_data.max_subqueries,
        )

        entities_resp = [
            ExtractedEntityResponse(
                name=e.name,
                category=e.category,
                value=e.value,
                is_explicit=e.is_explicit,
                confidence=e.confidence,
            )
            for e in plan.entities
        ]

        diag_resp = QueryDiagnosticsResponse(
            language_latency_ms=plan.diagnostics.language_latency_ms,
            normalization_latency_ms=plan.diagnostics.normalization_latency_ms,
            intent_latency_ms=plan.diagnostics.intent_latency_ms,
            entity_latency_ms=plan.diagnostics.entity_latency_ms,
            rewrite_latency_ms=plan.diagnostics.rewrite_latency_ms,
            expansion_latency_ms=plan.diagnostics.expansion_latency_ms,
            decomposition_latency_ms=plan.diagnostics.decomposition_latency_ms,
            total_understanding_ms=plan.diagnostics.total_understanding_ms,
            provider=plan.diagnostics.provider,
            model=plan.diagnostics.model,
            tokens_used=plan.diagnostics.tokens_used,
            cost_usd=plan.diagnostics.cost_usd,
            is_degraded=plan.diagnostics.is_degraded,
            degradation_reason=plan.diagnostics.degradation_reason,
        )

        plan_resp = SearchPlanResponse(
            original_query=plan.original_query,
            primary_query=plan.primary_query,
            alternative_queries=plan.alternative_queries,
            sub_queries=plan.sub_queries,
            language=plan.language,
            detected_languages=plan.detected_languages,
            intent=plan.intent,
            entities=entities_resp,
            hard_filters=plan.hard_filters,
            soft_filters=plan.soft_filters,
            confidence=plan.confidence,
            diagnostics=diag_resp,
        )

        return QueryAnalysisResponse(search_plan=plan_resp)

    except QueryValidationError as exc:
        raise ValidationAppException(message=str(exc)) from exc
    except QuerySafetyError as exc:
        raise BadRequestAppException(message=str(exc)) from exc
    except QueryTimeoutError as exc:
        raise AppException(
            message=f"Query analysis timed out: {exc}",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            code="QUERY_TIMEOUT",
        ) from exc
    except QueryProviderError as exc:
        raise AppException(
            message=f"Query understanding provider error: {exc}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="QUERY_PROVIDER_ERROR",
        ) from exc
    except QueryUnderstandingError as exc:
        raise AppException(
            message=f"Query understanding error: {exc}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="QUERY_UNDERSTANDING_ERROR",
        ) from exc
