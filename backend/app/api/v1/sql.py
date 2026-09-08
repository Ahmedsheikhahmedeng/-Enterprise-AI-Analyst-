"""REST API endpoint for Secure SQL Agent & Structured Data Analysis."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AppException,
    BadRequestAppException,
    ForbiddenAppException,
    NotFoundAppException,
    ValidationAppException,
)
from app.db.postgres import get_db_session
from app.rbac.catalog import PERM_ANALYTICS_EXECUTE
from app.schemas.common import ErrorResponse
from app.sql_agent.config import get_sql_agent_config
from app.sql_agent.exceptions import (
    SQLAgentError,
    SQLDataSourceNotFoundError,
    SQLProviderError,
    SQLResultSizeExceededError,
    SQLSecurityViolationError,
    SQLTenantMismatchError,
    SQLTimeoutError,
    SQLValidationError,
)
from app.sql_agent.schemas import (
    SQLAgentRequest,
    SQLAgentResponse,
    SQLAnalysisResponse,
    SQLProvenanceResponse,
    SQLQueryResultResponse,
)
from app.sql_agent.service import SQLAgentService
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/sql", tags=["SQL Agent"])


def get_sql_agent_service(request: Request) -> SQLAgentService:
    """Resolve or construct singleton SQLAgentService from application state."""
    existing = getattr(request.app.state, "sql_agent_service", None)
    if existing is not None and isinstance(existing, SQLAgentService):
        return existing

    service = SQLAgentService(config=get_sql_agent_config())
    request.app.state.sql_agent_service = service
    return service


@router.post(
    "/query",
    response_model=SQLAgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Natural Language to Secure SQL Execution & Analysis",
    description=(
        "Translates natural language questions into AST-validated, read-only "
        "PostgreSQL queries, executes them with statement timeouts, and computes "
        "controlled pandas analytical summaries."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Query executed and analyzed successfully"},
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Validation or security failure",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Tenant mismatch or permission denied",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Data source or dataset not found",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": "Generation provider error",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "model": ErrorResponse,
            "description": "Statement or execution timeout",
        },
    },
)
async def execute_sql_agent_query(
    request_data: SQLAgentRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_ANALYTICS_EXECUTE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[SQLAgentService, Depends(get_sql_agent_service)],
) -> SQLAgentResponse:
    """Execute natural language analytical query against tenant data source."""
    try:
        result = await service.execute_question(
            question=request_data.query,
            datasource_id=request_data.datasource_id,
            organization_id=tenant.organization_id,
            session=session,
            user_id=tenant.user_id,
            limit=request_data.limit,
            analyze=request_data.analyze,
        )

        analysis_resp = None
        if result.analysis is not None:
            analysis_resp = SQLAnalysisResponse(
                summary=result.analysis.summary,
                metrics=result.analysis.metrics,
                comparisons=result.analysis.comparisons,
                trends=result.analysis.trends,
            )

        return SQLAgentResponse(
            question=result.question,
            sql=result.generated_sql,
            query_result=SQLQueryResultResponse(
                columns=result.query_result.columns,
                rows=result.query_result.rows,
                row_count=result.query_result.row_count,
                truncated=result.query_result.truncated,
                duration_ms=round(result.query_result.duration_ms, 2),
            ),
            analysis=analysis_resp,
            provenance=SQLProvenanceResponse(
                sql_hash=result.provenance.sql_hash,
                datasource_id=result.provenance.datasource_id,
                tables_used=result.provenance.tables_used,
                columns_used=result.provenance.columns_used,
                row_count=result.provenance.row_count,
                duration_ms=round(result.provenance.duration_ms, 2),
            ),
            diagnostics=result.diagnostics,
        )

    except SQLTenantMismatchError as exc:
        raise ForbiddenAppException(message=str(exc)) from exc
    except SQLDataSourceNotFoundError as exc:
        raise NotFoundAppException(message=str(exc)) from exc
    except SQLSecurityViolationError as exc:
        raise BadRequestAppException(message=f"SQL Security Violation: {exc}") from exc
    except (SQLValidationError, SQLResultSizeExceededError) as exc:
        raise ValidationAppException(message=str(exc)) from exc
    except SQLTimeoutError as exc:
        raise AppException(
            message=str(exc),
            code="SQL_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        ) from exc
    except SQLProviderError as exc:
        raise AppException(
            message=str(exc),
            code="SQL_PROVIDER_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
        ) from exc
    except SQLAgentError as exc:
        raise BadRequestAppException(message=str(exc)) from exc
