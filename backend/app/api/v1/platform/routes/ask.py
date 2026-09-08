"""Canonical Ask API & Execution Management Routes — TASK 34."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.platform.coordinator import (
    CoordinatorRegistry,
    ExecutionEventCoordinator,
    get_coordinator_registry,
)
from app.api.v1.platform.dependencies import (
    check_rate_limit,
    get_correlation_ids,
    get_idempotency_manager,
)
from app.api.v1.platform.schemas.ask import (
    AskRequest,
    AskResponseData,
    AsyncAskResponseData,
)
from app.api.v1.platform.schemas.common import ApiResponse
from app.api.v1.platform.schemas.evidence import CitationItem, ProvenanceResponse
from app.api.v1.platform.schemas.execution import (
    ApprovalUIContract,
    CancellationResponse,
    ExecutionDetail,
)
from app.api.v1.platform.schemas.streaming import SSEEventType
from app.core.logging import get_logger
from app.db.postgres import get_db_session
from app.models.orchestration import OrchestrationExecutionModel
from app.rbac.catalog import (
    PERM_ORCHESTRATION_EXECUTE,
    PERM_ORCHESTRATION_READ,
)
from app.response_orchestration.api.routes import get_orchestration_service
from app.response_orchestration.application.orchestration_service import (
    ResponseOrchestrationService,
)
from app.response_orchestration.domain.enums import OrchestrationMode, ResponseStyle
from app.response_orchestration.domain.models import EnterpriseQueryRequest
from app.response_orchestration.infrastructure.repository import OrchestrationRepository
from app.security.replay import IdempotencyManager
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

logger = get_logger("platform.routes.ask")

ask_router = APIRouter(prefix="/ask", tags=["Platform Ask"])


async def _run_streaming_pipeline(
    execution_id: uuid.UUID,
    domain_req: EnterpriseQueryRequest,
    coordinator: ExecutionEventCoordinator,
    service: ResponseOrchestrationService,
    session_factory: Any,
    tenant_context: TenantContext,
) -> None:
    """Asynchronous background execution pipeline pushing ordered events and persisting to DB."""
    async with session_factory() as session:
        tracker = coordinator.progress_tracker

        try:
            # 1. Start UNDERSTANDING
            stage_prog = tracker.start_stage("UNDERSTANDING")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )
            await coordinator.emit_event(
                SSEEventType.EXECUTION_PROGRESS,
                {"progress": stage_prog.progress},
                session=session,
            )

            if coordinator.cancellation_token.is_set():
                return

            # Plan reasoning (Understanding + Semantic + Graph)
            plan = await service._plan_reasoning(
                question=domain_req.question,
                organization_id=domain_req.organization_id,
                mode=domain_req.mode,
                session=session,
                target_dataset_id=domain_req.target_dataset_id,
            )

            stage_prog = tracker.complete_stage("UNDERSTANDING")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )

            # 2. SEMANTIC Resolution
            stage_prog = tracker.start_stage("SEMANTIC")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )
            await coordinator.emit_event(
                SSEEventType.SEMANTIC_RESOLVED,
                {
                    "resolved_metrics": plan.resolved_metrics,
                    "resolved_dimensions": plan.resolved_dimensions,
                    "metrics_count": len(plan.resolved_metrics),
                },
                session=session,
            )
            stage_prog = tracker.complete_stage("SEMANTIC")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )

            if coordinator.cancellation_token.is_set():
                return

            # 3. GRAPH Reasoning
            stage_prog = tracker.start_stage("GRAPH")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )
            await coordinator.emit_event(
                SSEEventType.GRAPH_RESOLVED,
                {
                    "entity_nodes_count": len(plan.resolved_dimensions),
                    "strategy": plan.execution_strategy.value,
                },
                session=session,
            )
            stage_prog = tracker.complete_stage("GRAPH")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )

            # 4. PLANNING
            stage_prog = tracker.start_stage("PLANNING")
            stage_prog = tracker.complete_stage("PLANNING")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )

            if coordinator.cancellation_token.is_set():
                return

            # 5. EXECUTION (Retrieval / SQL)
            stage_prog = tracker.start_stage("EXECUTION")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )

            strat = plan.execution_strategy.value
            if strat in ("SQL", "HYBRID"):
                await coordinator.emit_event(
                    SSEEventType.SQL_STARTED,
                    {"strategy": strat},
                    session=session,
                )
            if strat in ("RAG", "HYBRID"):
                await coordinator.emit_event(
                    SSEEventType.RETRIEVAL_STARTED,
                    {"strategy": strat},
                    session=session,
                )

            # Execute full pipeline through orchestrator service
            result = await service.ask(
                request=domain_req,
                session=session,
                tenant_context=tenant_context,
            )

            if strat in ("SQL", "HYBRID"):
                await coordinator.emit_event(
                    SSEEventType.SQL_COMPLETED,
                    {"citations_count": len(result.citations)},
                    session=session,
                )
            if strat in ("RAG", "HYBRID"):
                await coordinator.emit_event(
                    SSEEventType.RETRIEVAL_COMPLETED,
                    {"citations_count": len(result.citations)},
                    session=session,
                )

            stage_prog = tracker.complete_stage("EXECUTION")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )

            # 6. EVIDENCE Collection
            stage_prog = tracker.start_stage("EVIDENCE")
            await coordinator.emit_event(
                SSEEventType.EVIDENCE_COLLECTED,
                {
                    "citations_count": len(result.citations),
                    "conflicts_count": len(result.conflicts),
                    "coverage": float(result.evidence_coverage),
                },
                session=session,
            )
            stage_prog = tracker.complete_stage("EVIDENCE")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )

            # 7. VERIFICATION & Decision
            stage_prog = tracker.start_stage("VERIFICATION")
            await coordinator.emit_event(
                SSEEventType.VERIFICATION_STARTED,
                {"confidence": float(result.confidence_score)},
                session=session,
            )
            await coordinator.emit_event(
                SSEEventType.DECISION_CREATED,
                {
                    "decision": result.decision.value,
                    "confidence": float(result.confidence_score),
                    "coverage": float(result.evidence_coverage),
                },
                session=session,
            )

            if result.decision.value == "APPROVAL_REQUIRED":
                await coordinator.emit_event(
                    SSEEventType.APPROVAL_REQUIRED,
                    {
                        "approval_required": True,
                        "risk_level": "HIGH",
                        "required_approvers": 1,
                    },
                    session=session,
                )

            stage_prog = tracker.complete_stage("VERIFICATION")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {
                    "stage": stage_prog.stage,
                    "status": stage_prog.status,
                    "progress": stage_prog.progress,
                },
                session=session,
            )

            # 8. RESPONSE Synthesis & Completion
            stage_prog = tracker.start_stage("RESPONSE")
            await coordinator.emit_event(
                SSEEventType.RESPONSE_GENERATING,
                {"mode": domain_req.mode},
                session=session,
            )

            # Emit response chunks for streaming feel
            chunk_size = 80
            answer_text = result.answer or ""
            for i in range(0, len(answer_text), chunk_size):
                chunk = answer_text[i : i + chunk_size]
                await coordinator.emit_event(
                    SSEEventType.RESPONSE_CHUNK,
                    {"chunk": chunk, "is_final": (i + chunk_size >= len(answer_text))},
                    session=session,
                )

            stage_prog = tracker.complete_stage("RESPONSE")
            await coordinator.emit_event(
                SSEEventType.EXECUTION_STAGE,
                {"stage": stage_prog.stage, "status": stage_prog.status, "progress": 100},
                session=session,
            )

            # Terminal Completion Event
            citations_data = [
                {
                    "id": c.citation_id,
                    "source_type": c.source_type.value,
                    "title": c.title,
                    "snippet": c.snippet,
                    "trust": c.trust_level,
                }
                for c in result.citations
            ]
            await coordinator.emit_event(
                SSEEventType.RESPONSE_COMPLETED,
                {
                    "answer": result.answer,
                    "decision": result.decision.value,
                    "confidence_score": float(result.confidence_score),
                    "evidence_coverage": float(result.evidence_coverage),
                    "citations": citations_data,
                    "warnings": result.warnings,
                },
                session=session,
            )

            await session.commit()
        except Exception as exc:
            logger.error(
                "Async streaming pipeline failed", execution_id=str(execution_id), error=str(exc)
            )
            await coordinator.emit_event(
                SSEEventType.EXECUTION_FAILED,
                {"error": "Pipeline execution encountered an internal error."},
                session=session,
            )
            await session.rollback()


@ask_router.post(
    "",
    summary="Canonical enterprise ask endpoint (Synchronous or SSE streaming)",
    dependencies=[Depends(check_rate_limit("ask", limit_per_minute=60))],
)
async def ask_endpoint(
    payload: AskRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_EXECUTE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ResponseOrchestrationService, Depends(get_orchestration_service)],
    registry: Annotated[CoordinatorRegistry, Depends(get_coordinator_registry)],
    idempotency_mgr: Annotated[IdempotencyManager, Depends(get_idempotency_manager)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ApiResponse[Any]:
    """Execute or stream canonical multi-modal AI reasoning pipeline."""
    req_id, tr_id = get_correlation_ids(request)

    # 1. Idempotency handling
    fingerprint = IdempotencyManager.compute_fingerprint(
        method="POST", path="/api/v1/ask", body=payload.model_dump_json()
    )
    if idempotency_key:
        is_new, record = await idempotency_mgr.acquire_or_check(
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            endpoint="/api/v1/ask",
            user_id=str(tenant_context.user_id),
            tenant_id=str(tenant_context.organization_id),
        )
        if not is_new and record.response_data:
            return ApiResponse.ok(data=record.response_data, request_id=req_id, trace_id=tr_id)

    try:
        mode_val = OrchestrationMode(payload.mode.upper())
    except (ValueError, AttributeError):
        mode_val = OrchestrationMode.AUTO

    try:
        style_val = ResponseStyle(payload.response_style.upper())
    except (ValueError, AttributeError):
        style_val = ResponseStyle.STANDARD

    domain_req = EnterpriseQueryRequest(
        question=payload.question,
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        conversation_id=payload.conversation_id,
        mode=mode_val,
        response_style=style_val,
        target_dataset_id=payload.target_dataset_id,
        enable_clarification=payload.enable_clarification,
    )

    # 2. Synchronous branch when stream=False
    if not payload.stream:
        result = await service.ask(
            request=domain_req,
            session=session,
            tenant_context=tenant_context,
        )
        citations = [
            CitationItem(
                id=c.citation_id,
                source_type=c.source_type.value,
                title=c.title,
                snippet=c.snippet,
                trust=c.trust_level,
                confidence=1.0,
            )
            for c in result.citations
        ]
        conflicts = [
            {
                "conflict_id": cf.conflict_id,
                "field": cf.field,
                "source_a": cf.source_a,
                "value_a": cf.value_a,
                "source_b": cf.source_b,
                "value_b": cf.value_b,
                "severity": cf.severity,
                "description": cf.description,
            }
            for cf in result.conflicts
        ]
        approval_contract = None
        if result.decision.value == "APPROVAL_REQUIRED":
            approval_contract = ApprovalUIContract(
                approval_required=True,
                risk_level="HIGH",
                required_approvers=1,
            )

        resp_data = AskResponseData(
            execution_id=result.execution_id,
            answer=result.answer,
            status=result.status.value,
            decision=result.decision.value,
            confidence_score=float(result.confidence_score),
            evidence_coverage=float(result.evidence_coverage),
            citations=citations,
            conflicts=conflicts,
            warnings=result.warnings,
            clarification_prompt=result.clarification_prompt,
            approval=approval_contract,
            provenance=result.provenance,
            diagnostics=result.diagnostics,
        )

        if idempotency_key:
            await idempotency_mgr.record_completion(
                idempotency_key=idempotency_key,
                tenant_id=str(tenant_context.organization_id),
                response_data=resp_data.model_dump(),
            )

        return ApiResponse.ok(data=resp_data, request_id=req_id, trace_id=tr_id)

    # 3. Asynchronous streaming branch when stream=True
    execution_id = uuid.uuid4()
    now = datetime.now(UTC)

    # Create initial execution record in database
    exec_record = OrchestrationExecutionModel(
        id=execution_id,
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        conversation_id=payload.conversation_id,
        query=payload.question,
        mode=payload.mode,
        status="RUNNING",
        decision="PENDING",
        started_at=now,
    )
    session.add(exec_record)
    await session.commit()

    # Create coordinator and emit execution.started
    coordinator = await registry.get_or_create(
        execution_id=execution_id,
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
    )
    await coordinator.emit_event(
        SSEEventType.EXECUTION_STARTED,
        {"mode": payload.mode, "question": payload.question},
        session=session,
    )
    await session.commit()

    # Dispatch background task for pipeline execution
    session_factory = request.app.state.db_session_factory
    background_tasks.add_task(
        _run_streaming_pipeline,
        execution_id=execution_id,
        domain_req=domain_req,
        coordinator=coordinator,
        service=service,
        session_factory=session_factory,
        tenant_context=tenant_context,
    )

    async_data = AsyncAskResponseData(
        execution_id=execution_id,
        status="RUNNING",
        stream_url=f"/api/v1/ask/{execution_id}/stream",
        events_url=f"/api/v1/ask/{execution_id}/events",
        created_at=now.isoformat(),
    )

    if idempotency_key:
        await idempotency_mgr.record_completion(
            idempotency_key=idempotency_key,
            tenant_id=str(tenant_context.organization_id),
            response_data=async_data.model_dump(),
        )

    return ApiResponse.ok(data=async_data, request_id=req_id, trace_id=tr_id)


@ask_router.get(
    "/{execution_id}",
    response_model=ApiResponse[ExecutionDetail],
    summary="Get execution details by ID",
    dependencies=[Depends(check_rate_limit("execution_detail", limit_per_minute=120))],
)
async def get_execution_detail(
    execution_id: uuid.UUID,
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ExecutionDetail]:
    """Retrieve full execution record enforcing tenant isolation."""
    req_id, tr_id = get_correlation_ids(request)
    repo = OrchestrationRepository(session)
    record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or access denied.",
        )

    citations = [
        CitationItem(
            id=c.get("citation_id", "C1"),
            source_type=c.get("source_type", "UNKNOWN"),
            title=c.get("title", ""),
            snippet=c.get("snippet", ""),
            trust=c.get("trust_level", "DIRECT"),
            confidence=1.0,
        )
        for c in (record.citations or [])
    ]

    detail = ExecutionDetail(
        id=record.id,
        query=record.query,
        status=record.status,
        mode=record.mode,
        execution_strategy=record.execution_strategy,
        decision=record.decision,
        confidence_score=float(record.confidence_score),
        evidence_coverage=float(record.evidence_coverage),
        answer=record.answer,
        clarification_prompt=record.clarification_prompt,
        citations=citations,
        conflicts=record.conflicts or [],
        warnings=record.warnings or [],
        provenance=record.provenance or {},
        diagnostics=record.diagnostics or {},
        started_at=record.started_at,
        completed_at=record.completed_at,
    )

    return ApiResponse.ok(data=detail, request_id=req_id, trace_id=tr_id)


@ask_router.get(
    "/{execution_id}/provenance",
    response_model=ApiResponse[ProvenanceResponse],
    summary="Get provenance graph and lineage for an execution",
    dependencies=[Depends(check_rate_limit("provenance", limit_per_minute=120))],
)
async def get_execution_provenance(
    execution_id: uuid.UUID,
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ProvenanceResponse]:
    """Retrieve detailed reasoning lineage and evidence DAG."""
    req_id, tr_id = get_correlation_ids(request)
    repo = OrchestrationRepository(session)
    record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or access denied.",
        )

    citations = [
        CitationItem(
            id=c.get("citation_id", "C1"),
            source_type=c.get("source_type", "UNKNOWN"),
            title=c.get("title", ""),
            snippet=c.get("snippet", ""),
            trust=c.get("trust_level", "DIRECT"),
            confidence=1.0,
        )
        for c in (record.citations or [])
    ]

    prov_data = ProvenanceResponse(
        execution_id=record.id,
        mode=record.mode,
        strategy=record.execution_strategy,
        stages=(record.provenance or {}).get("stages", []),
        citations=citations,
        diagnostics=record.diagnostics or {},
    )

    return ApiResponse.ok(data=prov_data, request_id=req_id, trace_id=tr_id)


@ask_router.get(
    "/{execution_id}/evidence",
    response_model=ApiResponse[list[CitationItem]],
    summary="Get citations and evidence items for an execution",
    dependencies=[Depends(check_rate_limit("evidence", limit_per_minute=120))],
)
async def get_execution_evidence(
    execution_id: uuid.UUID,
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[list[CitationItem]]:
    """Retrieve interactive citations matching UX contract."""
    req_id, tr_id = get_correlation_ids(request)
    repo = OrchestrationRepository(session)
    record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or access denied.",
        )

    citations = [
        CitationItem(
            id=c.get("citation_id", "C1"),
            source_type=c.get("source_type", "UNKNOWN"),
            title=c.get("title", ""),
            snippet=c.get("snippet", ""),
            trust=c.get("trust_level", "DIRECT"),
            confidence=1.0,
        )
        for c in (record.citations or [])
    ]

    return ApiResponse.ok(data=citations, request_id=req_id, trace_id=tr_id)


@ask_router.post(
    "/{execution_id}/cancel",
    response_model=ApiResponse[CancellationResponse],
    summary="Cancel in-flight execution",
    dependencies=[Depends(check_rate_limit("cancel", limit_per_minute=60))],
)
async def cancel_execution(
    execution_id: uuid.UUID,
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_EXECUTE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    registry: Annotated[CoordinatorRegistry, Depends(get_coordinator_registry)],
) -> ApiResponse[CancellationResponse]:
    """Cancel a running execution and signal downstream tasks."""
    req_id, tr_id = get_correlation_ids(request)
    repo = OrchestrationRepository(session)
    record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or access denied.",
        )

    prev_status = record.status
    if record.status in ("COMPLETED", "FAILED", "CANCELLED"):
        cancel_resp = CancellationResponse(
            execution_id=execution_id,
            previous_status=prev_status,
            current_status=record.status,
            cancelled_at=datetime.now(UTC).isoformat(),
        )
        return ApiResponse.ok(data=cancel_resp, request_id=req_id, trace_id=tr_id)

    # Signal coordinator
    coord = await registry.get(execution_id)
    if coord and coord.organization_id == tenant_context.organization_id:
        await coord.cancel(reason="Client explicitly requested cancellation", session=session)

    record.status = "CANCELLED"
    record.completed_at = datetime.now(UTC)
    session.add(record)
    await session.commit()

    cancel_resp = CancellationResponse(
        execution_id=execution_id,
        previous_status=prev_status,
        current_status="CANCELLED",
        cancelled_at=datetime.now(UTC).isoformat(),
    )

    return ApiResponse.ok(data=cancel_resp, request_id=req_id, trace_id=tr_id)


@ask_router.post(
    "/preview",
    response_model=ApiResponse[dict[str, Any]],
    summary="Preview reasoning strategy and semantic matches without full synthesis",
)
async def preview_query(
    payload: AskRequest,
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_EXECUTE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ResponseOrchestrationService, Depends(get_orchestration_service)],
) -> ApiResponse[dict[str, Any]]:
    """Preview reasoning plan, metrics resolution, and clarification needs."""
    req_id, tr_id = get_correlation_ids(request)
    try:
        mode_val = OrchestrationMode(payload.mode.upper())
    except (ValueError, AttributeError):
        mode_val = OrchestrationMode.AUTO

    plan = await service._plan_reasoning(
        question=payload.question,
        organization_id=tenant_context.organization_id,
        mode=mode_val,
        session=session,
        target_dataset_id=payload.target_dataset_id,
    )
    preview_data = {
        "strategy": plan.execution_strategy.value,
        "resolved_metrics": plan.resolved_metrics,
        "resolved_dimensions": plan.resolved_dimensions,
        "requires_clarification": plan.requires_clarification,
        "clarification_options": plan.clarification_options,
    }
    return ApiResponse.ok(data=preview_data, request_id=req_id, trace_id=tr_id)


@ask_router.get(
    "/{execution_id}/diagnostics",
    response_model=ApiResponse[dict[str, Any]],
    summary="Get execution diagnostics by ID",
)
async def get_execution_diagnostics(
    execution_id: uuid.UUID,
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[dict[str, Any]]:
    """Retrieve execution diagnostics for performance analysis."""
    req_id, tr_id = get_correlation_ids(request)
    repo = OrchestrationRepository(session)
    record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or access denied.",
        )
    return ApiResponse.ok(data=record.diagnostics or {}, request_id=req_id, trace_id=tr_id)
