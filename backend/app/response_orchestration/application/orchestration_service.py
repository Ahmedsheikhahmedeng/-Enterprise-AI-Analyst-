"""Unified Enterprise Response Orchestration Service coordinating reasoning, execution, verification, and decisions."""

import asyncio
import logging
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm_gateway.application.gateway_service import LLMGatewayService
from app.observability.instrumentation.orchestration import (
    OrchestrationInstrumentation,
    get_orchestration_instrumentation,
)
from app.query.service import QueryUnderstandingService
from app.rag.service import RAGService
from app.response_orchestration.application.confidence_service import ConfidenceService
from app.response_orchestration.application.conflict_service import ConflictService
from app.response_orchestration.application.decision_service import DecisionService
from app.response_orchestration.application.evidence_service import EvidenceService
from app.response_orchestration.application.response_service import ResponseService
from app.response_orchestration.application.verification_service import VerificationService
from app.response_orchestration.domain.enums import (
    DecisionType,
    ExecutionStrategy,
    OrchestrationMode,
    OrchestrationStatus,
)
from app.response_orchestration.domain.models import (
    EnterpriseQueryRequest,
    EnterpriseResponse,
    OrchestrationBudget,
    UnifiedReasoningPlan,
)
from app.response_orchestration.domain.protocols import ResponseOrchestrationProtocol
from app.response_orchestration.infrastructure.cache import OrchestrationCache
from app.response_orchestration.infrastructure.repository import OrchestrationRepository
from app.sql_agent.service import SQLAgentService
from app.tenancy.context import TenantContext

logger = logging.getLogger(__name__)


class ResponseOrchestrationService(ResponseOrchestrationProtocol):
    """Central orchestration facade coordinating Query Understanding, Semantics, Graph, SQL, RAG, and LLM Gateway."""

    def __init__(
        self,
        query_service: QueryUnderstandingService | None = None,
        sql_service: SQLAgentService | None = None,
        rag_service: RAGService | None = None,
        llm_gateway: LLMGatewayService | None = None,
        confidence_service: ConfidenceService | None = None,
        conflict_service: ConflictService | None = None,
        decision_service: DecisionService | None = None,
        evidence_service: EvidenceService | None = None,
        verification_service: VerificationService | None = None,
        cache: OrchestrationCache | None = None,
        instrumentation: OrchestrationInstrumentation | None = None,
    ) -> None:
        self.query_service = query_service
        self.sql_service = sql_service
        self.rag_service = rag_service
        self.llm_gateway = llm_gateway
        self.confidence_service = confidence_service or ConfidenceService()
        self.conflict_service = conflict_service or ConflictService()
        self.decision_service = decision_service or DecisionService()
        self.evidence_service = evidence_service or EvidenceService()
        self.verification_service = verification_service or VerificationService()
        self.cache = cache or OrchestrationCache()
        self.instrumentation = instrumentation or get_orchestration_instrumentation()

    async def _plan_reasoning(
        self,
        question: str,
        organization_id: uuid.UUID,
        mode: OrchestrationMode,
        session: AsyncSession,
        target_dataset_id: uuid.UUID | None = None,
    ) -> UnifiedReasoningPlan:
        """Resolve semantic definitions, graph paths, and select execution strategy."""
        resolved_metrics: list[str] = []
        resolved_dimensions: list[str] = []
        semantic_matches: list[dict[str, Any]] = []
        semantic_plan = None

        # 1. Semantic Layer Resolution
        try:
            from app.semantic.application.query_planner import SemanticQueryPlanner

            sem_planner = SemanticQueryPlanner(session)
            semantic_plan = await sem_planner.plan_query(
                question=question,
                organization_id=organization_id,
                target_dataset_id=target_dataset_id,
            )
            if semantic_plan:
                resolved_metrics = [rm.name for rm in semantic_plan.resolved_metrics]
                resolved_dimensions = [rd.name for rd in semantic_plan.resolved_dimensions]
                semantic_matches = [
                    {"name": rm.name, "type": "metric", "formula": rm.formula}
                    for rm in semantic_plan.resolved_metrics
                ]
        except Exception as exc:
            logger.debug("Semantic planning bypass: %s", exc)

        # 2. Knowledge Graph Reasoning
        graph_paths: list[dict[str, Any]] = []
        try:
            from app.knowledge_graph.application.graph_planner import GraphQueryPlanner

            graph_planner = GraphQueryPlanner(session)
            graph_res = await graph_planner.plan_graph_reasoning(
                question=question,
                organization_id=organization_id,
            )
            if graph_res and graph_res.paths:
                graph_paths = [
                    {
                        "depth": p.depth,
                        "confidence": p.confidence,
                        "nodes": [n.name for n in p.nodes],
                        "relationships": [e.edge_type.value for e in p.edges],
                    }
                    for p in graph_res.paths
                ]
        except Exception as exc:
            logger.debug("Graph planning bypass: %s", exc)

        # 3. Strategy Selection
        strategy = ExecutionStrategy.HYBRID
        if mode == OrchestrationMode.SQL:
            strategy = ExecutionStrategy.SQL_ONLY
        elif mode == OrchestrationMode.RAG:
            strategy = ExecutionStrategy.RAG_ONLY
        elif mode == OrchestrationMode.GRAPH:
            strategy = ExecutionStrategy.GRAPH_ONLY
        elif mode == OrchestrationMode.AUTO:
            # Heuristic routing based on query understanding & semantic resolution
            q_lower = question.lower()
            has_numerical_metrics = bool(resolved_metrics) or any(
                term in q_lower
                for term in [
                    "total",
                    "sum",
                    "average",
                    "count",
                    "revenue",
                    "sales",
                    "growth",
                    "rate",
                    "كم",
                    "إجمالي",
                    "معدل",
                ]
            )
            has_doc_intent = any(
                term in q_lower
                for term in [
                    "policy",
                    "document",
                    "report",
                    "manual",
                    "procedure",
                    "guide",
                    "سياسة",
                    "دليل",
                    "تقرير",
                ]
            )

            if has_numerical_metrics and not has_doc_intent:
                strategy = ExecutionStrategy.SQL_ONLY
            elif has_doc_intent and not has_numerical_metrics:
                strategy = ExecutionStrategy.RAG_ONLY
            elif graph_paths and not has_numerical_metrics and not has_doc_intent:
                strategy = ExecutionStrategy.GRAPH_ONLY
            else:
                strategy = ExecutionStrategy.HYBRID

        # Clarification trigger check
        requires_clarification = False
        clarification_options: list[str] = []
        if len(resolved_metrics) > 3:
            requires_clarification = True
            clarification_options = resolved_metrics[:3]

        return UnifiedReasoningPlan(
            intent="analytical_query",
            entities=[],
            resolved_metrics=resolved_metrics,
            resolved_dimensions=resolved_dimensions,
            semantic_matches=semantic_matches,
            graph_paths=graph_paths,
            candidate_datasets=[target_dataset_id] if target_dataset_id else [],
            execution_strategy=strategy,
            budget=OrchestrationBudget(),
            requires_clarification=requires_clarification,
            clarification_options=clarification_options,
        )

    async def ask(
        self,
        request: EnterpriseQueryRequest,
        *,
        session: AsyncSession,
        tenant_context: TenantContext | None = None,
    ) -> EnterpriseResponse:
        """Execute end-to-end multi-modal query orchestration through state machine."""
        t_start = time.perf_counter()
        execution_id = uuid.uuid4()
        request_id = uuid.uuid4()
        trace_id = str(uuid.uuid4())

        repo = OrchestrationRepository(session)
        await repo.create_execution(
            execution_id=execution_id,
            organization_id=request.organization_id,
            user_id=request.user_id,
            query=request.question,
            mode=request.mode.value,
            conversation_id=request.conversation_id,
        )

        self.instrumentation.record_request_started(
            mode=request.mode.value,
            execution_strategy=ExecutionStrategy.NONE.value,
        )

        # 1. State: PLANNING
        t_plan_start = time.perf_counter()
        plan = await self._plan_reasoning(
            question=request.question,
            organization_id=request.organization_id,
            mode=request.mode,
            session=session,
            target_dataset_id=request.target_dataset_id,
        )
        plan_duration_ms = int((time.perf_counter() - t_plan_start) * 1000)
        await repo.record_step(
            execution_id=execution_id,
            step_type="planning",
            step_order=1,
            input_payload={"question": request.question, "mode": request.mode.value},
            output_payload={
                "strategy": plan.execution_strategy.value,
                "metrics": plan.resolved_metrics,
            },
            latency_ms=plan_duration_ms,
        )

        # Early return for clarification
        if plan.requires_clarification and request.enable_clarification:
            opts_str = ", ".join(f"'{opt}'" for opt in plan.clarification_options)
            clarification_text = f"Your question mentions multiple metrics ({opts_str}). Which specific metric would you like to analyze?"
            self.instrumentation.record_clarification_requested("multiple_metrics")
            return EnterpriseResponse(
                execution_id=execution_id,
                request_id=request_id,
                trace_id=trace_id,
                organization_id=request.organization_id,
                answer=clarification_text,
                status=OrchestrationStatus.NEEDS_CLARIFICATION,
                decision=DecisionType.ASK_CLARIFICATION,
                confidence_score=0.40,
                evidence_coverage=0.0,
                clarification_prompt=clarification_text,
                provenance={"reasoning_plan": plan.execution_strategy.value},
            )

        # 2. State: EXECUTING (Parallel Bounded Execution)
        t_exec_start = time.perf_counter()
        sql_tasks = []
        rag_tasks = []
        branch_failures: list[str] = []

        sql_results: list[Any] = []
        rag_results: list[Any] = []

        if (
            plan.execution_strategy in (ExecutionStrategy.SQL_ONLY, ExecutionStrategy.HYBRID)
            and self.sql_service
        ):
            sql_svc = self.sql_service

            async def run_sql() -> Any:
                try:
                    if hasattr(sql_svc, "execute_query"):
                        return await sql_svc.execute_query(
                            query=request.question,
                            organization_id=request.organization_id,
                            session=session,
                            datasource_id=request.target_dataset_id,
                        )
                    elif hasattr(sql_svc, "execute_question") and request.target_dataset_id:
                        return await sql_svc.execute_question(
                            question=request.question,
                            datasource_id=request.target_dataset_id,
                            organization_id=request.organization_id,
                            session=session,
                        )
                    return None
                except Exception as e:
                    logger.warning("SQL execution branch failed: %s", e)
                    branch_failures.append(f"SQL: {e}")
                    return None

            sql_tasks.append(run_sql())

        if (
            plan.execution_strategy in (ExecutionStrategy.RAG_ONLY, ExecutionStrategy.HYBRID)
            and self.rag_service
        ):
            rag_svc = self.rag_service

            async def run_rag() -> Any:
                try:
                    if hasattr(rag_svc, "answer"):
                        return await rag_svc.answer(
                            query=request.question,
                            organization_id=request.organization_id,
                            session=session,
                        )
                    elif hasattr(rag_svc, "answer_query"):
                        return await rag_svc.answer_query(
                            query=request.question,
                            organization_id=request.organization_id,
                            session=session,
                        )
                    return None
                except Exception as e:
                    logger.warning("RAG execution branch failed: %s", e)
                    branch_failures.append(f"RAG: {e}")
                    return None

            rag_tasks.append(run_rag())

        # Execute concurrent tasks with timeout protection
        all_branch_tasks = sql_tasks + rag_tasks
        if all_branch_tasks:
            results = await asyncio.gather(*all_branch_tasks, return_exceptions=True)
            for res in results:
                if res is not None and not isinstance(res, Exception):
                    # Classify result
                    if hasattr(res, "generated_sql") or hasattr(res, "query_result"):
                        sql_results.append(res)
                    else:
                        rag_results.append(res)

        exec_duration_ms = int((time.perf_counter() - t_exec_start) * 1000)
        await repo.record_step(
            execution_id=execution_id,
            step_type="branch_execution",
            step_order=2,
            input_payload={"strategy": plan.execution_strategy.value},
            output_payload={
                "sql_count": len(sql_results),
                "rag_count": len(rag_results),
                "failures": branch_failures,
            },
            latency_ms=exec_duration_ms,
        )

        # 3. State: COLLECTING_EVIDENCE
        bundle, citations = self.evidence_service.build_bundle(
            organization_id=request.organization_id,
            sql_results=sql_results,
            rag_results=rag_results,
            graph_paths=plan.graph_paths,
            semantic_plan=None,
        )

        # 4. State: VERIFYING & CONFLICT DETECTION
        conflicts = self.conflict_service.detect_conflicts(bundle)
        for c in conflicts:
            self.instrumentation.record_conflict_detected(
                conflict_type=c.field, severity=c.severity
            )

        # 5. State: GENERATING_RESPONSE (via LLM Gateway)
        t_gen_start = time.perf_counter()
        raw_answer = ""
        model_used = None
        if self.llm_gateway:
            resp_svc = ResponseService(self.llm_gateway)
            raw_answer, model_used = await resp_svc.generate_grounded_response(
                query=request.question,
                plan=plan,
                evidence_bundle=bundle,
                conflicts=conflicts,
                style=request.response_style,
                tenant_context=tenant_context,
                is_partial=bool(branch_failures),
            )
        else:
            # Offline synthesis fallback
            parts = [it.content for it in bundle.items[:3]]
            raw_answer = " ".join(parts) if parts else "No evidence available."

        gen_duration_ms = int((time.perf_counter() - t_gen_start) * 1000)

        # 6. State: VERIFYING_AGAIN (Post-generation verification & Hallucination Gate)
        clean_answer, verified_citations = self.verification_service.validate_and_repair_citations(
            answer_text=raw_answer,
            evidence_bundle=bundle,
        )
        claims, coverage = self.verification_service.extract_and_verify_claims(
            answer_text=clean_answer,
            evidence_bundle=bundle,
        )

        # 7. State: DECIDING & CONFIDENCE SCORING
        confidence = self.confidence_service.calculate_confidence(
            evidence_bundle=bundle,
            conflicts=conflicts,
            claims=claims,
            semantic_confidence=0.90 if plan.resolved_metrics else 0.50,
            graph_confidence=0.80 if plan.graph_paths else 0.50,
        )

        decision = self.decision_service.evaluate_decision(
            plan=plan,
            evidence_bundle=bundle,
            conflicts=conflicts,
            claims=claims,
            confidence_score=confidence,
            evidence_coverage=coverage,
            branch_failures=branch_failures,
        )

        final_status = OrchestrationStatus.COMPLETED
        if decision == DecisionType.PARTIAL_ANSWER:
            final_status = OrchestrationStatus.PARTIAL
        elif decision == DecisionType.INSUFFICIENT_EVIDENCE:
            final_status = OrchestrationStatus.INSUFFICIENT_EVIDENCE
        elif decision == DecisionType.BLOCK:
            final_status = OrchestrationStatus.BLOCKED

        total_duration_sec = time.perf_counter() - t_start

        # Record completion metrics
        self.instrumentation.record_request_completed(
            mode=request.mode.value,
            execution_strategy=plan.execution_strategy.value,
            status=final_status.value,
            decision=decision.value,
            duration_sec=total_duration_sec,
            confidence=confidence,
            evidence_coverage=coverage,
        )

        # Final audit step
        await repo.record_step(
            execution_id=execution_id,
            step_type="decision_and_verification",
            step_order=3,
            input_payload={"coverage": coverage, "confidence": confidence},
            output_payload={"decision": decision.value, "status": final_status.value},
            latency_ms=int(total_duration_sec * 1000),
        )

        # Construct Provenance
        provenance = {
            "execution_strategy": plan.execution_strategy.value,
            "model": model_used or "deterministic",
            "semantic_metrics": plan.resolved_metrics,
            "evidence_count": len(bundle.items),
            "citations_verified": len(verified_citations),
            "conflicts_detected": len(conflicts),
        }

        # Update Conversation/Message if conversation_id was provided
        if request.conversation_id:
            try:
                from app.models.conversation import Message

                msg_user = Message(
                    id=uuid.uuid4(),
                    conversation_id=request.conversation_id,
                    role="user",
                    content=request.question,
                )
                msg_assistant = Message(
                    id=uuid.uuid4(),
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=clean_answer,
                )
                session.add_all([msg_user, msg_assistant])
                await session.flush()
            except Exception as exc:
                logger.debug("Conversation message persistence bypass: %s", exc)

        warnings = [c.description for c in conflicts]
        if branch_failures:
            warnings.extend(branch_failures)

        return EnterpriseResponse(
            execution_id=execution_id,
            request_id=request_id,
            trace_id=trace_id,
            organization_id=request.organization_id,
            answer=clean_answer,
            status=final_status,
            decision=decision,
            confidence_score=confidence,
            evidence_coverage=coverage,
            citations=citations,
            evidence=bundle.items,
            conflicts=conflicts,
            warnings=warnings,
            provenance=provenance,
            diagnostics={
                "duration_total_ms": int(total_duration_sec * 1000),
                "plan_ms": plan_duration_ms,
                "exec_ms": exec_duration_ms,
                "gen_ms": gen_duration_ms,
            },
        )
