"""Central AIAnalystService orchestrating planning, multi-source execution,
and grounded synthesis.
"""

import time
import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.config import AnalystConfig, get_analyst_config
from app.analyst.conflicts import ConflictDetector
from app.analyst.executor import ParallelAnalystExecutor
from app.analyst.merger import EvidenceMerger
from app.analyst.models import (
    AnalystDiagnostics,
    AnalystResult,
    AnalystRouteType,
    BranchType,
    DataConflict,
    ExecutionPlan,
    UnifiedEvidence,
)
from app.analyst.planner import DeterministicAnalystPlanner
from app.analyst.policies import AnalystSecurityPolicy
from app.analyst.provenance import AnalystProvenanceTracker
from app.core.logging import get_logger
from app.models.analysis import AnalysisRun, AnalysisStep
from app.models.audit import AuditLog
from app.models.usage import UsageEvent
from app.rag.grounding import GroundingValidator
from app.rag.models import Evidence, RAGAnswerResult
from app.rag.service import RAGService
from app.sql_agent.models import SQLAgentResult
from app.sql_agent.service import SQLAgentService

logger = get_logger("analyst.service")


class AIAnalystService:
    """Enterprise AI Analyst orchestrating multi-modal questions across SQL and RAG."""

    def __init__(
        self,
        sql_service: SQLAgentService | None = None,
        rag_service: RAGService | None = None,
        config: AnalystConfig | None = None,
    ) -> None:
        self.sql_service = sql_service
        self.rag_service = rag_service
        self.config = config or get_analyst_config()
        self.planner = DeterministicAnalystPlanner(config=self.config)
        self.executor = ParallelAnalystExecutor(
            sql_service=self.sql_service,
            rag_service=self.rag_service,
            config=self.config,
        )
        self.merger = EvidenceMerger(max_evidence=self.config.max_evidence)
        self.conflict_detector = ConflictDetector()
        self.grounding_validator = GroundingValidator()
        self.security_policy = AnalystSecurityPolicy()

    async def ask(
        self,
        query: str,
        organization_id: UUID,
        *,
        session: AsyncSession,
        user_id: UUID | None = None,
        datasource_id: UUID | None = None,
        limit: int | None = None,
        top_k: int | None = None,
    ) -> AnalystResult:
        """Process user question across structured databases and unstructured documents."""
        t_total_start = time.perf_counter()
        diagnostics = AnalystDiagnostics()

        from app.observability.instrumentation.analyst import get_analyst_instrumentation
        from app.observability.tracing import get_trace_manager

        trace_mgr = get_trace_manager()
        analyst_instr = get_analyst_instrumentation()

        # 1. Security & Tenant Validation
        if datasource_id:
            await self.security_policy.validate_datasource_access(
                datasource_id=datasource_id,
                organization_id=organization_id,
                session=session,
            )

        # 1.5 Semantic Resolution & Graph Reasoning
        semantic_plan = None
        graph_paths = None
        try:
            from app.semantic.application.query_planner import SemanticQueryPlanner

            semantic_planner = SemanticQueryPlanner(session)
            semantic_plan = await semantic_planner.plan_query(
                question=query,
                organization_id=organization_id,
            )
        except Exception as exc:
            logger.debug("Semantic resolution fallback: %s", exc)

        try:
            from app.knowledge_graph.application.graph_planner import GraphQueryPlanner

            graph_planner = GraphQueryPlanner(session)
            graph_res = await graph_planner.plan_graph_reasoning(
                question=query,
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
            logger.debug("Knowledge graph reasoning fallback: %s", exc)

        # 2. Planning
        t_plan = time.perf_counter()
        with trace_mgr.start_span_sync(
            "analyst.plan",
            attributes={"datasource_id": str(datasource_id) if datasource_id else None},
        ):
            plan: ExecutionPlan = self.planner.plan(
                query=query,
                datasource_id=datasource_id,
                limit=limit,
                top_k=top_k,
            )
        diagnostics.planning_ms = (time.perf_counter() - t_plan) * 1000
        diagnostics.route_selected = plan.route.value

        # 3. Create persistent AnalysisRun
        analysis_run_id = uuid.uuid4()
        try:
            run = AnalysisRun(
                id=analysis_run_id,
                organization_id=organization_id,
                user_id=user_id or uuid.uuid4(),
                query=query,
                status="running",
                started_at=datetime.now(UTC),
            )
            session.add(run)
            await session.flush()
        except Exception as exc:
            logger.warning("Failed to initialize AnalysisRun: %s", exc)

        # 4. Concurrent Execution
        branch_results = await self.executor.execute_plan(
            plan=plan,
            organization_id=organization_id,
            session=session,
            user_id=user_id,
            analysis_run_id=analysis_run_id,
            semantic_plan=semantic_plan,
            graph_paths=graph_paths,
        )

        diagnostics.branches_executed = len(branch_results)

        # Separate SQL and RAG branch results
        sql_agent_results: list[SQLAgentResult] = []
        rag_agent_results: list[RAGAnswerResult] = []
        failed_branches: list[str] = []

        for br in branch_results:
            if br.branch_type == BranchType.SQL:
                diagnostics.sql_ms += br.latency_ms
                if br.success and isinstance(br.data, SQLAgentResult):
                    sql_agent_results.append(br.data)
                else:
                    failed_branches.append(f"SQL({br.branch_id}): {br.error}")
            elif br.branch_type == BranchType.RAG:
                diagnostics.rag_ms += br.latency_ms
                if br.success and isinstance(br.data, RAGAnswerResult):
                    rag_agent_results.append(br.data)
                else:
                    failed_branches.append(f"RAG({br.branch_id}): {br.error}")

        # Check for degradation
        is_partial = False
        is_degraded = False
        degradation_reason = None
        if failed_branches:
            is_degraded = True
            degradation_reason = "; ".join(failed_branches)
            diagnostics.degraded = True
            diagnostics.degradation_reason = degradation_reason
            if sql_agent_results or rag_agent_results:
                is_partial = True

        # 5. Evidence Merging
        t_merge = time.perf_counter()
        with trace_mgr.start_span_sync("analyst.merge"):
            unified_evidence: list[UnifiedEvidence] = self.merger.merge(
                sql_results=sql_agent_results,
                rag_results=rag_agent_results,
            )
        diagnostics.merge_ms = (time.perf_counter() - t_merge) * 1000

        # 6. Conflict Detection
        t_conf = time.perf_counter()
        with trace_mgr.start_span_sync("analyst.conflict_detection"):
            conflicts = self.conflict_detector.detect(unified_evidence)
        diagnostics.conflict_ms = (time.perf_counter() - t_conf) * 1000

        # 7. Answer Generation & Grounding
        t_gen = time.perf_counter()
        with trace_mgr.start_span_sync("analyst.final_generation"):
            answer_text, claimed_citations = self._synthesize_answer(
                query=query,
                route=plan.route,
                sql_results=sql_agent_results,
                rag_results=rag_agent_results,
                evidence=unified_evidence,
                conflicts=conflicts,
                is_partial=is_partial,
            )
        diagnostics.generation_ms = (time.perf_counter() - t_gen) * 1000

        # Validate citations with GroundingValidator
        validator_evidence: list[Evidence] = [
            Evidence(
                evidence_id=ue.evidence_id,
                chunk_id=uuid.UUID(ue.metadata.get("chunk_id", str(uuid.uuid4()))),
                document_id=uuid.UUID(ue.metadata.get("document_id", str(uuid.uuid4()))),
                organization_id=organization_id,
                rank=idx + 1,
                rerank_score=ue.confidence,
                text=ue.text,
                page_number=ue.metadata.get("page_number"),
                document_name=ue.title,
            )
            for idx, ue in enumerate(unified_evidence)
        ]

        t_val = time.perf_counter()
        with trace_mgr.start_span_sync("analyst.validation"):
            grounded_answer = self.grounding_validator.validate_and_repair(
                raw_answer=answer_text,
                claimed_evidence_ids=claimed_citations,
                claimed_grounded=bool(unified_evidence),
                claimed_confidence=0.90 if unified_evidence else 0.0,
                available_evidence=validator_evidence,
            )
        validation_ms = (time.perf_counter() - t_val) * 1000

        diagnostics.total_ms = (time.perf_counter() - t_total_start) * 1000

        # Record Analyst Telemetry & Metrics
        analyst_instr.record_stage_latency(
            "planning", diagnostics.planning_ms, route=plan.route.value
        )
        analyst_instr.record_stage_latency("sql", diagnostics.sql_ms, route=plan.route.value)
        analyst_instr.record_stage_latency("rag", diagnostics.rag_ms, route=plan.route.value)
        analyst_instr.record_stage_latency("merge", diagnostics.merge_ms, route=plan.route.value)
        analyst_instr.record_stage_latency(
            "conflict", diagnostics.conflict_ms, route=plan.route.value
        )
        analyst_instr.record_stage_latency(
            "generation", diagnostics.generation_ms, route=plan.route.value
        )
        analyst_instr.record_stage_latency("validation", validation_ms, route=plan.route.value)
        analyst_instr.record_stage_latency("total", diagnostics.total_ms, route=plan.route.value)

        is_ar = any("\u0600" <= c <= "\u06ff" for c in query)
        lang = "ar" if is_ar else "en"
        analyst_status = "degraded" if is_degraded else "success"
        analyst_instr.record_analyst_request(
            route=plan.route.value,
            status=analyst_status,
            language=lang,
            duration_ms=diagnostics.total_ms,
            is_degraded=is_degraded,
        )

        # Build clean citations
        citations = AnalystProvenanceTracker.build_citations(
            evidence=unified_evidence,
            cited_ids=set(grounded_answer.evidence_ids),
        )
        citations_dicts = [c.model_dump() for c in citations]

        # 8. Record Telemetry & Audit
        try:
            audit = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="analyst_query",
                resource_type="analyst",
                resource_id=str(analysis_run_id),
                metadata_={
                    "query": query,
                    "route": plan.route.value,
                    "is_partial": is_partial,
                    "evidence_count": len(unified_evidence),
                    "conflicts_count": len(conflicts),
                    "duration_ms": diagnostics.total_ms,
                },
            )
            usage = UsageEvent(
                organization_id=organization_id,
                user_id=user_id,
                event_type="analyst_query",
                quantity=1,
                metadata_={"route": plan.route.value, "plan_id": str(plan.plan_id)},
            )
            session.add_all([audit, usage])

            # Update AnalysisRun
            if "run" in locals() and run is not None:
                run.status = "completed" if not is_degraded else "partial"
                run.completed_at = datetime.now(UTC)

            run_stmt = AnalysisStep(
                analysis_run_id=analysis_run_id,
                step_type="analyst_synthesis",
                step_order=10,
                status="completed" if not is_degraded else "partial",
                input_payload={"query": query, "route": plan.route.value},
                output_payload={
                    "answer": grounded_answer.answer,
                    "grounded": grounded_answer.grounded,
                    "confidence": grounded_answer.confidence,
                    "route": plan.route.value,
                    "evidence_cited": grounded_answer.evidence_ids,
                    "conflicts_detected": len(conflicts),
                    "citations": citations_dicts,
                    "conflicts": [
                        {
                            "field": c.field,
                            "source_a": c.source_a,
                            "value_a": c.value_a,
                            "source_b": c.source_b,
                            "value_b": c.value_b,
                            "severity": c.severity,
                            "description": c.description,
                        }
                        for c in conflicts
                    ],
                    "evidence": [
                        {
                            "evidence_id": ev.evidence_id,
                            "source_type": ev.source_type,
                            "title": ev.title,
                            "content": ev.text,
                            "is_calculated": ev.is_calculated,
                            "metadata": ev.metadata,
                        }
                        for ev in unified_evidence
                    ],
                    "diagnostics": diagnostics.__dict__,
                    "sql_rows": [
                        row
                        for res in sql_agent_results
                        if res.query_result and res.query_result.rows
                        for row in res.query_result.rows
                    ],
                    "sql_metrics": {
                        k: v
                        for res in sql_agent_results
                        if res.analysis and res.analysis.metrics
                        for k, v in res.analysis.metrics.items()
                    },
                },
            )
            session.add(run_stmt)
            await session.commit()
        except Exception as exc:
            logger.warning("Failed to record Analyst audit telemetry: %s", exc)
            await session.rollback()

        return AnalystResult(
            answer=grounded_answer.answer,
            route=plan.route,
            grounded=grounded_answer.grounded,
            confidence=grounded_answer.confidence,
            is_partial=is_partial,
            is_degraded=is_degraded,
            conflicts=conflicts,
            evidence=unified_evidence,
            citations=citations_dicts,
            diagnostics=diagnostics,
            execution_plan=plan,
            analysis_run_id=analysis_run_id,
        )

    def _synthesize_answer(
        self,
        query: str,
        route: AnalystRouteType,
        sql_results: list[SQLAgentResult],
        rag_results: list[RAGAnswerResult],
        evidence: list[UnifiedEvidence],
        conflicts: list[DataConflict],
        is_partial: bool,
    ) -> tuple[str, list[str]]:
        """Synthesize a coherent grounded answer attributing sources clearly."""
        if not evidence:
            return "No relevant structured data or document evidence found to answer the query.", []

        claimed_citations: list[str] = []
        answer_parts: list[str] = []

        # SQL summary contribution
        if sql_results:
            sql_citations = [ev.evidence_id for ev in evidence if ev.source_type == "sql"]
            claimed_citations.extend(sql_citations)
            primary_tag = sql_citations[0] if sql_citations else "S1"

            sr = sql_results[0]
            if sr.analysis and sr.analysis.summary:
                answer_parts.append(f"{sr.analysis.summary} [{primary_tag}]")
            elif sr.query_result.rows:
                first_row = sr.query_result.rows[0]
                summary = ", ".join(f"{k}: {v}" for k, v in first_row.items())
                answer_parts.append(f"Structured analysis indicates: {summary} [{primary_tag}]")

        # RAG contribution
        if rag_results:
            rr = rag_results[0]
            rag_citations = [ev.evidence_id for ev in evidence if ev.source_type == "document"]
            claimed_citations.extend(rag_citations)
            primary_tag = rag_citations[0] if rag_citations else "R1"

            if rr.answer and rr.answer.answer:
                # Replace internal legacy tags [E#] with unified [R#]
                clean_rag = rr.answer.answer
                clean_rag = clean_rag.replace("[E1]", f"[{primary_tag}]")
                if not any(tag in clean_rag for tag in ["[R1]", "[R2]"]):
                    clean_rag = f"{clean_rag} [{primary_tag}]"
                answer_parts.append(clean_rag)

        # Conflict disclosure
        if conflicts:
            conflict_notes = []
            for c in conflicts:
                msg = (
                    f"Discrepancy noted: structured data reports {c.value_a} ({c.source_a}) "
                    f"while document sources state {c.value_b} ({c.source_b})."
                )
                conflict_notes.append(msg)
            answer_parts.append(" ".join(conflict_notes))

        # Partial degradation disclosure
        if is_partial:
            msg = "(Note: Analysis is partial due to an execution failure in one data branch.)"
            answer_parts.append(msg)

        final_text = "\n\n".join(answer_parts).strip()
        return final_text, claimed_citations
