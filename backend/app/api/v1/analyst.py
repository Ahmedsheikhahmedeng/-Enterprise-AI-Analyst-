"""REST API endpoint for the Unified AI Analyst Orchestrator."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.config import get_analyst_config
from app.analyst.exceptions import (
    AnalystBudgetExceededError,
    AnalystError,
    AnalystRoutingError,
    AnalystTenantMismatchError,
    AnalystTimeoutError,
)
from app.analyst.schemas import (
    AnalystDiagnosticsResponse,
    AnalystQueryRequest,
    AnalystQueryResponse,
    CitationItem,
    DataConflictItem,
)
from app.analyst.service import AIAnalystService
from app.core.exceptions import (
    AppException,
    BadRequestAppException,
    ForbiddenAppException,
    ValidationAppException,
)
from app.db.postgres import get_db_session
from app.rag.service import RAGService
from app.rbac.catalog import PERM_ANALYTICS_EXECUTE
from app.schemas.common import ErrorResponse
from app.sql_agent.service import SQLAgentService
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/analyst", tags=["AI Analyst"])


def get_analyst_service(request: Request) -> AIAnalystService:
    """Resolve or construct singleton AIAnalystService from application state."""
    existing = getattr(request.app.state, "analyst_service", None)
    if existing is not None and isinstance(existing, AIAnalystService):
        return existing

    sql_service = getattr(request.app.state, "sql_agent_service", None)
    if sql_service is None:
        sql_service = SQLAgentService()
        request.app.state.sql_agent_service = sql_service

    rag_service = getattr(request.app.state, "rag_service", None)
    if (
        rag_service is None
        and getattr(request.app.state, "hybrid_retrieval_service", None) is not None
    ):
        from app.rag.config import get_rag_config

        rag_service = RAGService(
            hybrid_retrieval_service=request.app.state.hybrid_retrieval_service,
            config=get_rag_config(),
        )
        request.app.state.rag_service = rag_service

    service = AIAnalystService(
        sql_service=sql_service,
        rag_service=rag_service,
        config=get_analyst_config(),
    )
    request.app.state.analyst_service = service
    return service


@router.post(
    "/ask",
    response_model=AnalystQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask Unified Enterprise AI Analyst",
    description=(
        "Unified entrypoint for cross-modal analytical reasoning over structured SQL databases "
        "and unstructured document repositories with evidence synthesis and conflict detection."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters"},
        403: {"model": ErrorResponse, "description": "Tenant mismatch or forbidden access"},
        422: {"model": ErrorResponse, "description": "Validation or routing error"},
        429: {"model": ErrorResponse, "description": "Budget limit exceeded"},
        504: {"model": ErrorResponse, "description": "Execution timeout"},
    },
)
async def ask_analyst(
    body: AnalystQueryRequest,
    request: Request,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_ANALYTICS_EXECUTE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AnalystQueryResponse:
    """Execute unified multi-modal query across structured and unstructured enterprise assets."""
    service = get_analyst_service(request)

    try:
        res = await service.ask(
            query=body.query,
            organization_id=tenant.organization_id,
            session=session,
            user_id=tenant.user_id,
            datasource_id=body.datasource_id,
            limit=body.limit,
            top_k=body.top_k,
        )

        routes_list: list[str] = []
        if res.execution_plan:
            for b in res.execution_plan.branches:
                if b.branch_type.value not in routes_list:
                    routes_list.append(b.branch_type.value)
        if not routes_list:
            routes_list = [res.route.value]

        citations = [CitationItem(**c) for c in res.citations]
        conflicts = [
            DataConflictItem(
                field=c.field,
                source_a=c.source_a,
                value_a=c.value_a,
                source_b=c.source_b,
                value_b=c.value_b,
                severity=c.severity,
                description=c.description,
            )
            for c in res.conflicts
        ]

        diagnostics_resp = AnalystDiagnosticsResponse(
            planning_ms=res.diagnostics.planning_ms,
            sql_ms=res.diagnostics.sql_ms,
            rag_ms=res.diagnostics.rag_ms,
            merge_ms=res.diagnostics.merge_ms,
            conflict_ms=res.diagnostics.conflict_ms,
            generation_ms=res.diagnostics.generation_ms,
            total_ms=res.diagnostics.total_ms,
            branches_executed=res.diagnostics.branches_executed,
            degraded=res.diagnostics.degraded,
            degradation_reason=res.diagnostics.degradation_reason,
        )

        return AnalystQueryResponse(
            answer=res.answer,
            grounded=res.grounded,
            confidence=res.confidence,
            routes=routes_list,
            citations=citations,
            conflicts=conflicts,
            is_partial=res.is_partial,
            diagnostics=diagnostics_resp,
        )

    except AnalystTenantMismatchError as exc:
        raise ForbiddenAppException(message=exc.message, details=exc.details) from exc
    except AnalystRoutingError as exc:
        raise ValidationAppException(message=exc.message, details=exc.details) from exc
    except AnalystTimeoutError as exc:
        raise AppException(
            message=exc.message,
            code="GATEWAY_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=exc.details,
        ) from exc
    except AnalystBudgetExceededError as exc:
        raise BadRequestAppException(message=exc.message, details=exc.details) from exc
    except AnalystError as exc:
        raise BadRequestAppException(message=exc.message, details=exc.details) from exc
