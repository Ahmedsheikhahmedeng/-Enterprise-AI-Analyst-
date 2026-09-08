"""FastAPI REST routes for Enterprise Continuous AI Evaluation, Benchmarking & Quality Monitoring."""

import uuid
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous_evaluation.api.schemas import (
    BaselineUpdateRequest,
    BenchmarkCreateRequest,
    BenchmarkResponse,
    CalibrationAnalysisResponse,
    CalibrationBucketResponse,
    ComparisonRequest,
    ComparisonResponse,
    EvaluationSuiteCreateRequest,
    EvaluationSuiteResponse,
    HumanEvaluationCreateRequest,
    HumanEvaluationResponse,
    ProductionSampleCreateRequest,
    ProductionSampleResponse,
    QualityGateCreateRequest,
    QualityGateEvaluateRequest,
    QualityGateResponse,
    QualityGateResultResponse,
    RegressionFindingResponse,
)
from app.continuous_evaluation.application.benchmark_service import BenchmarkService
from app.continuous_evaluation.application.calibration_service import CalibrationService
from app.continuous_evaluation.application.comparison_service import ComparisonService
from app.continuous_evaluation.application.evaluation_service import ContinuousEvaluationService
from app.continuous_evaluation.application.monitoring_service import MonitoringService
from app.continuous_evaluation.application.quality_gate_service import QualityGateService
from app.continuous_evaluation.application.regression_service import RegressionService
from app.continuous_evaluation.application.release_service import ReleaseQualityPolicy
from app.continuous_evaluation.domain.errors import (
    BenchmarkNotFoundError,
    QualityGateNotFoundError,
)
from app.continuous_evaluation.domain.models import QualityGateRule
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol
from app.continuous_evaluation.infrastructure.repository import ContinuousEvaluationRepository
from app.db.postgres import get_db_session
from app.rbac.catalog import (
    PERM_EVALUATION_BENCHMARK_MANAGE,
    PERM_EVALUATION_HUMAN_REVIEW,
    PERM_EVALUATION_MONITOR_READ,
    PERM_EVALUATION_QUALITY_GATE_READ,
    PERM_EVALUATION_RUN_EXECUTE,
)
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/evaluation", tags=["Continuous Evaluation & Quality Monitoring"])


@dataclass
class EvaluationServices:
    repo: ContinuousEvaluationRepositoryProtocol
    benchmark: BenchmarkService
    evaluation: ContinuousEvaluationService
    regression: RegressionService
    gate: QualityGateService
    calibration: CalibrationService
    comparison: ComparisonService
    monitoring: MonitoringService
    release: ReleaseQualityPolicy


def _get_services(db: AsyncSession) -> EvaluationServices:
    repo = ContinuousEvaluationRepository(db)
    return EvaluationServices(
        repo=repo,
        benchmark=BenchmarkService(repo),
        evaluation=ContinuousEvaluationService(repo),
        regression=RegressionService(repo),
        gate=QualityGateService(repo),
        calibration=CalibrationService(repo),
        comparison=ComparisonService(repo),
        monitoring=MonitoringService(repo),
        release=ReleaseQualityPolicy(),
    )


# --- Benchmarks & Suites ---


@router.post("/benchmarks", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED)
async def create_benchmark(
    payload: BenchmarkCreateRequest,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_BENCHMARK_MANAGE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BenchmarkResponse:
    svcs = _get_services(session)
    benchmark = await svcs.benchmark.create_benchmark(
        organization_id=tenant.organization_id,
        name=payload.name,
        task_type=payload.task_type,
        target=payload.target,
        dataset_id=payload.dataset_id,
        description=payload.description,
        version=payload.version,
    )
    await session.commit()
    return BenchmarkResponse(
        id=benchmark.id,
        organization_id=benchmark.organization_id,
        name=benchmark.name,
        description=benchmark.description,
        task_type=benchmark.task_type,
        target=benchmark.target.value,
        dataset_id=benchmark.dataset_id,
        version=benchmark.version,
        baseline_run_id=benchmark.baseline_run_id,
        status=benchmark.status,
        created_at=benchmark.created_at,
    )


@router.get("/benchmarks", response_model=list[BenchmarkResponse])
async def list_benchmarks(
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_MONITOR_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    target: str | None = None,
    task_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[BenchmarkResponse]:
    svcs = _get_services(session)
    benchmarks = await svcs.benchmark.list_benchmarks(
        organization_id=tenant.organization_id,
        target=target,
        task_type=task_type,
        limit=limit,
        offset=offset,
    )
    return [
        BenchmarkResponse(
            id=b.id,
            organization_id=b.organization_id,
            name=b.name,
            description=b.description,
            task_type=b.task_type,
            target=b.target.value,
            dataset_id=b.dataset_id,
            version=b.version,
            baseline_run_id=b.baseline_run_id,
            status=b.status,
            created_at=b.created_at,
        )
        for b in benchmarks
    ]


@router.get("/benchmarks/{benchmark_id}", response_model=BenchmarkResponse)
async def get_benchmark(
    benchmark_id: uuid.UUID,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_MONITOR_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BenchmarkResponse:
    svcs = _get_services(session)
    try:
        b = await svcs.benchmark.get_benchmark(benchmark_id, tenant.organization_id)
        return BenchmarkResponse(
            id=b.id,
            organization_id=b.organization_id,
            name=b.name,
            description=b.description,
            task_type=b.task_type,
            target=b.target.value,
            dataset_id=b.dataset_id,
            version=b.version,
            baseline_run_id=b.baseline_run_id,
            status=b.status,
            created_at=b.created_at,
        )
    except BenchmarkNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.post("/benchmarks/{benchmark_id}/baseline", response_model=BenchmarkResponse)
async def set_benchmark_baseline(
    benchmark_id: uuid.UUID,
    payload: BaselineUpdateRequest,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_BENCHMARK_MANAGE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BenchmarkResponse:
    svcs = _get_services(session)
    try:
        b = await svcs.benchmark.set_baseline_run(
            benchmark_id, payload.baseline_run_id, tenant.organization_id
        )
        await session.commit()
        return BenchmarkResponse(
            id=b.id,
            organization_id=b.organization_id,
            name=b.name,
            description=b.description,
            task_type=b.task_type,
            target=b.target.value,
            dataset_id=b.dataset_id,
            version=b.version,
            baseline_run_id=b.baseline_run_id,
            status=b.status,
            created_at=b.created_at,
        )
    except BenchmarkNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


# --- Evaluation Suites ---


@router.post("/suites", response_model=EvaluationSuiteResponse, status_code=status.HTTP_201_CREATED)
async def create_suite(
    payload: EvaluationSuiteCreateRequest,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_BENCHMARK_MANAGE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EvaluationSuiteResponse:
    svcs = _get_services(session)
    suite = await svcs.benchmark.create_suite(
        organization_id=tenant.organization_id,
        name=payload.name,
        benchmark_ids=payload.benchmark_ids,
        description=payload.description,
        version=payload.version,
    )
    await session.commit()
    return EvaluationSuiteResponse(
        id=suite.id,
        organization_id=suite.organization_id,
        name=suite.name,
        description=suite.description,
        benchmark_ids=suite.benchmark_ids,
        version=suite.version,
        status=suite.status,
        created_at=suite.created_at,
    )


@router.get("/suites", response_model=list[EvaluationSuiteResponse])
async def list_suites(
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_MONITOR_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[EvaluationSuiteResponse]:
    svcs = _get_services(session)
    suites = await svcs.benchmark.list_suites(tenant.organization_id, limit=limit, offset=offset)
    return [
        EvaluationSuiteResponse(
            id=s.id,
            organization_id=s.organization_id,
            name=s.name,
            description=s.description,
            benchmark_ids=s.benchmark_ids,
            version=s.version,
            status=s.status,
            created_at=s.created_at,
        )
        for s in suites
    ]


# --- Regressions ---


@router.get("/regressions", response_model=list[RegressionFindingResponse])
async def list_regressions(
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_MONITOR_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    run_id: uuid.UUID | None = None,
    severity: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[RegressionFindingResponse]:
    svcs = _get_services(session)
    regressions = await svcs.repo.list_regressions(
        organization_id=tenant.organization_id,
        run_id=run_id,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return [
        RegressionFindingResponse(
            benchmark_id=r.benchmark_id,
            run_id=r.run_id,
            baseline_run_id=r.baseline_run_id,
            metric_name=r.metric_name,
            baseline_value=r.baseline_value,
            current_value=r.current_value,
            drop_percentage=r.drop_percentage,
            severity=r.severity,
            details=r.details,
            is_statistically_significant=r.is_statistically_significant,
            p_value=r.p_value,
        )
        for r in regressions
    ]


# --- Quality Gates ---


@router.post("/quality-gates", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_quality_gate(
    payload: QualityGateCreateRequest,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_BENCHMARK_MANAGE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    svcs = _get_services(session)
    rules = [
        QualityGateRule(
            metric_name=r.metric_name,
            min_threshold=r.min_threshold,
            max_threshold=r.max_threshold,
            max_drop_percentage=r.max_drop_percentage,
            is_critical=r.is_critical,
        )
        for r in payload.rules
    ]
    gate_id = await svcs.gate.create_gate(
        organization_id=tenant.organization_id,
        name=payload.name,
        rules=rules,
        description=payload.description,
    )
    await session.commit()
    return {"gate_id": str(gate_id), "status": "CREATED"}


@router.get("/quality-gates", response_model=list[QualityGateResponse])
async def list_quality_gates(
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_QUALITY_GATE_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[QualityGateResponse]:
    svcs = _get_services(session)
    gates = await svcs.gate.list_gates(tenant.organization_id)
    return [QualityGateResponse(**g) for g in gates]


@router.post("/quality-gates/evaluate", response_model=QualityGateResultResponse)
async def evaluate_quality_gate(
    payload: QualityGateEvaluateRequest,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_RUN_EXECUTE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QualityGateResultResponse:
    svcs = _get_services(session)
    try:
        res = await svcs.gate.evaluate_gate(
            gate_id=payload.gate_id,
            run_id=payload.run_id,
            scorecard=payload.scorecard,
            organization_id=tenant.organization_id,
        )
        await session.commit()
        return QualityGateResultResponse(
            gate_id=res.gate_id,
            run_id=res.run_id,
            decision=res.decision,
            scorecard=res.scorecard,
            violations=res.violations,
        )
    except QualityGateNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


# --- Differential Comparison ---


@router.post("/compare", response_model=ComparisonResponse)
async def compare_scorecards(
    payload: ComparisonRequest,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_MONITOR_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComparisonResponse:
    svcs = _get_services(session)
    report = svcs.comparison.compare_scorecards(
        comparison_type=payload.comparison_type,
        baseline_id=payload.baseline_id,
        candidate_id=payload.candidate_id,
        baseline_scorecard=payload.baseline_scorecard,
        candidate_scorecard=payload.candidate_scorecard,
    )
    return ComparisonResponse(
        comparison_type=report.comparison_type,
        baseline_id=report.baseline_id,
        candidate_id=report.candidate_id,
        metrics_diff=report.metrics_diff,
        winner=report.winner,
        summary=report.summary,
    )


# --- Confidence Calibration ---


@router.get("/calibration", response_model=CalibrationAnalysisResponse)
async def get_calibration(
    run_id: uuid.UUID,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_MONITOR_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CalibrationAnalysisResponse:
    svcs = _get_services(session)
    cal = await svcs.calibration.get_calibration(run_id, tenant.organization_id)
    if not cal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Calibration for run {run_id} not found"
        )
    return CalibrationAnalysisResponse(
        run_id=cal.run_id,
        ece=cal.ece,
        brier_score=cal.brier_score,
        buckets=[
            CalibrationBucketResponse(
                bin_start=b.bin_start,
                bin_end=b.bin_end,
                avg_confidence=b.avg_confidence,
                accuracy=b.accuracy,
                sample_count=b.sample_count,
            )
            for b in cal.buckets
        ],
    )


# --- Production Quality Sampling ---


@router.get("/production-quality", response_model=list[ProductionSampleResponse])
async def list_production_samples(
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_MONITOR_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    strategy: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ProductionSampleResponse]:
    svcs = _get_services(session)
    samples = await svcs.repo.list_production_samples(
        tenant.organization_id, strategy=strategy, limit=limit, offset=offset
    )
    return [
        ProductionSampleResponse(
            id=s.id,
            organization_id=s.organization_id,
            query=s.query,
            response=s.response,
            sampling_strategy=s.sampling_strategy.value,
            data_sensitivity=s.data_sensitivity,
            redacted=s.redacted,
            expires_at=s.expires_at,
            source_execution_id=s.source_execution_id,
            created_at=s.created_at,
        )
        for s in samples
    ]


@router.post(
    "/production-quality",
    response_model=ProductionSampleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_production_sample(
    payload: ProductionSampleCreateRequest,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_MONITOR_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductionSampleResponse:
    svcs = _get_services(session)
    sample = await svcs.monitoring.capture_production_sample(
        organization_id=tenant.organization_id,
        query=payload.query,
        response=payload.response,
        strategy=payload.sampling_strategy,
        data_sensitivity=payload.data_sensitivity,
        retention_days=payload.retention_days,
        source_execution_id=payload.source_execution_id,
    )
    await session.commit()
    return ProductionSampleResponse(
        id=sample.id,
        organization_id=sample.organization_id,
        query=sample.query,
        response=sample.response,
        sampling_strategy=sample.sampling_strategy.value,
        data_sensitivity=sample.data_sensitivity,
        redacted=sample.redacted,
        expires_at=sample.expires_at,
        source_execution_id=sample.source_execution_id,
        created_at=sample.created_at,
    )


# --- Human Review ---


@router.post(
    "/human-evaluation",
    response_model=HumanEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_human_evaluation(
    payload: HumanEvaluationCreateRequest,
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_EVALUATION_HUMAN_REVIEW))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HumanEvaluationResponse:
    svcs = _get_services(session)
    try:
        h = await svcs.monitoring.record_human_review(
            organization_id=tenant.organization_id,
            evaluator_id=payload.evaluator_id,
            accuracy_score=payload.accuracy_score,
            helpfulness_score=payload.helpfulness_score,
            grounding_score=payload.grounding_score,
            clarity_score=payload.clarity_score,
            sample_id=payload.sample_id,
            case_result_id=payload.case_result_id,
            comments=payload.comments,
        )
        await session.commit()
        return HumanEvaluationResponse(
            id=h.id,
            organization_id=h.organization_id,
            evaluator_id=h.evaluator_id,
            sample_id=h.sample_id,
            case_result_id=h.case_result_id,
            accuracy_score=h.accuracy_score,
            helpfulness_score=h.helpfulness_score,
            grounding_score=h.grounding_score,
            clarity_score=h.clarity_score,
            normalized_score=h.normalized_score(),
            comments=h.comments,
            evaluation_source=h.evaluation_source.value,
            created_at=h.created_at,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
