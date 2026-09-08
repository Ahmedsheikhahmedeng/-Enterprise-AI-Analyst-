"""FastAPI REST router for Enterprise AI Evaluation & Quality Framework."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.service import AIAnalystService
from app.api.v1.analyst import get_analyst_service
from app.db.postgres import get_db_session
from app.evaluation.schemas import (
    CompareEvaluationRunsRequest,
    CreateEvaluationCaseRequest,
    CreateEvaluationDatasetRequest,
    EvaluationCaseListResponse,
    EvaluationCaseResponse,
    EvaluationCaseResultResponse,
    EvaluationDatasetListResponse,
    EvaluationDatasetResponse,
    EvaluationRunResponse,
    RegressionReportResponse,
    ScorecardResponse,
    StartEvaluationRunRequest,
)
from app.evaluation.service import EvaluationService
from app.rbac.catalog import (
    PERM_EVALUATION_COMPARE,
    PERM_EVALUATION_CREATE,
    PERM_EVALUATION_READ,
    PERM_EVALUATION_RUN,
)
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


def get_evaluation_service(request: Request) -> EvaluationService:
    """Resolve or construct singleton EvaluationService from application state."""
    existing = getattr(request.app.state, "evaluation_service", None)
    if existing is not None and isinstance(existing, EvaluationService):
        return existing
    service = EvaluationService()
    request.app.state.evaluation_service = service
    return service


# =========================================================================
# Datasets Endpoints
# =========================================================================


@router.post(
    "/datasets",
    response_model=EvaluationDatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new evaluation dataset",
)
async def create_dataset(
    payload: CreateEvaluationDatasetRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_CREATE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationDatasetResponse:
    """Initialize a versioned evaluation dataset scoped to the tenant."""
    dataset = await service.create_dataset(
        session=session,
        organization_id=tenant.organization_id,
        name=payload.name,
        description=payload.description,
        language=payload.language,
        user_id=tenant.user_id,
    )
    return EvaluationDatasetResponse.model_validate(dataset)


@router.get(
    "/datasets",
    response_model=EvaluationDatasetListResponse,
    summary="List evaluation datasets",
)
async def list_datasets(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> EvaluationDatasetListResponse:
    """List all benchmark datasets belonging to the tenant."""
    items, total = await service.list_datasets(
        session=session,
        organization_id=tenant.organization_id,
        page=page,
        page_size=page_size,
    )
    return EvaluationDatasetListResponse(
        items=[EvaluationDatasetResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# =========================================================================
# Cases Endpoints
# =========================================================================


@router.post(
    "/datasets/{dataset_id}/cases",
    response_model=EvaluationCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add evaluation case to dataset",
)
async def add_case(
    dataset_id: UUID,
    payload: CreateEvaluationCaseRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_CREATE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationCaseResponse:
    """Add a ground truth benchmark case to an evaluation dataset."""
    case = await service.add_case(
        session=session,
        organization_id=tenant.organization_id,
        dataset_id=dataset_id,
        query=payload.query,
        route_expected=payload.route_expected,
        language=payload.language,
        datasource_id=payload.datasource_id,
        expected_answer=payload.expected_answer,
        expected_citations=payload.expected_citations,
        expected_documents=payload.expected_documents,
        expected_sql_semantics=payload.expected_sql_semantics,
        expected_metrics=payload.expected_metrics,
        expected_rows=payload.expected_rows,
        relevant_chunks=payload.relevant_chunks,
        tags=payload.tags,
        difficulty=payload.difficulty,
        user_id=tenant.user_id,
    )
    return EvaluationCaseResponse.model_validate(case)


@router.get(
    "/datasets/{dataset_id}/cases",
    response_model=EvaluationCaseListResponse,
    summary="List evaluation cases in dataset",
)
async def list_cases(
    dataset_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> EvaluationCaseListResponse:
    """Retrieve test cases for a given evaluation dataset."""
    cases, total = await service.list_cases(
        session=session,
        organization_id=tenant.organization_id,
        dataset_id=dataset_id,
        limit=limit,
        offset=offset,
    )
    return EvaluationCaseListResponse(
        items=[EvaluationCaseResponse.model_validate(c) for c in cases],
        total=total,
    )


# =========================================================================
# Runs Endpoints
# =========================================================================


@router.post(
    "/runs",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an evaluation benchmark run",
)
async def start_run(
    payload: StartEvaluationRunRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_RUN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    analyst_service: Annotated[AIAnalystService, Depends(get_analyst_service)],
) -> EvaluationRunResponse:
    """Execute benchmark test suite against the unified analyst pipeline."""
    run, _ = await service.run_benchmark(
        session=session,
        analyst_service=analyst_service,
        organization_id=tenant.organization_id,
        dataset_id=payload.dataset_id,
        dataset_version=payload.dataset_version,
        max_cases=payload.max_cases,
        tags=payload.tags,
        user_id=tenant.user_id,
    )
    return EvaluationRunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}",
    response_model=EvaluationRunResponse,
    summary="Get evaluation run details",
)
async def get_run(
    run_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationRunResponse:
    """Retrieve details and status for a benchmark run."""
    run = await service.get_run(
        session=session,
        organization_id=tenant.organization_id,
        run_id=run_id,
    )
    return EvaluationRunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}/results",
    response_model=list[EvaluationCaseResultResponse],
    summary="Get individual case results of an evaluation run",
)
async def get_run_results(
    run_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> list[EvaluationCaseResultResponse]:
    """Retrieve fine-grained case-level scoring results for a benchmark run."""
    results = await service.get_run_results(
        session=session,
        organization_id=tenant.organization_id,
        run_id=run_id,
    )
    return [EvaluationCaseResultResponse.model_validate(r) for r in results]


@router.get(
    "/runs/{run_id}/scorecard",
    response_model=ScorecardResponse,
    summary="Get scorecard for an evaluation run",
)
async def get_scorecard(
    run_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> ScorecardResponse:
    """Generate aggregate quality, performance, and cost scorecard."""
    scorecard = await service.get_scorecard(
        session=session,
        organization_id=tenant.organization_id,
        run_id=run_id,
    )
    return ScorecardResponse(**scorecard.to_dict())


@router.post(
    "/runs/{run_id}/compare",
    response_model=RegressionReportResponse,
    summary="Compare evaluation run against a baseline",
)
async def compare_runs(
    run_id: UUID,
    payload: CompareEvaluationRunsRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_COMPARE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> RegressionReportResponse:
    """Perform regression detection comparing candidate run against baseline."""
    report = await service.compare_runs(
        session=session,
        organization_id=tenant.organization_id,
        baseline_run_id=payload.baseline_run_id,
        candidate_run_id=run_id,
        user_id=tenant.user_id,
    )
    return RegressionReportResponse(**report.to_dict())
