"""Central SQLAgentService orchestrating schema discovery, SQL generation,
validation, and analytics.
"""

import time
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.analysis import AnalysisStep
from app.models.audit import AuditLog
from app.models.usage import LLMRequest, UsageEvent
from app.sql_agent.analyzer import SQLResultAnalyzer
from app.sql_agent.config import SQLAgentConfig, get_sql_agent_config
from app.sql_agent.executor import ReadOnlySQLExecutor
from app.sql_agent.models import SQLAgentResult
from app.sql_agent.planner import SQLPlanner
from app.sql_agent.provenance import SQLProvenanceTracker
from app.sql_agent.providers.base import SQLGenerationProvider
from app.sql_agent.providers.factory import SQLProviderFactory
from app.sql_agent.schema import SchemaDiscoveryService
from app.sql_agent.validator import SQLSecurityValidator

logger = get_logger("sql_agent.service")


class SQLAgentService:
    """Orchestrates natural language to safe SQL analysis over relational datasets."""

    def __init__(
        self,
        schema_discovery_service: SchemaDiscoveryService | None = None,
        provider: SQLGenerationProvider | None = None,
        config: SQLAgentConfig | None = None,
    ) -> None:
        self.config = config or get_sql_agent_config()
        self.schema_discovery = schema_discovery_service or SchemaDiscoveryService(self.config)
        self.provider = provider or SQLProviderFactory.create(self.config)
        self.planner = SQLPlanner()
        self.validator = SQLSecurityValidator(self.config)
        self.executor = ReadOnlySQLExecutor(self.config)
        self.analyzer = SQLResultAnalyzer()

    async def execute_question(
        self,
        question: str,
        datasource_id: UUID,
        organization_id: UUID,
        *,
        session: AsyncSession,
        user_id: UUID | None = None,
        limit: int | None = None,
        analyze: bool = True,
        analysis_run_id: UUID | None = None,
        semantic_plan: Any | None = None,
        graph_paths: list[dict[str, Any]] | None = None,
        graph_context: dict[str, Any] | None = None,
    ) -> SQLAgentResult:
        """Execute end-to-end question answering pipeline over structured data."""
        t_total_start = time.perf_counter()
        diagnostics: dict[str, Any] = {
            "provider": self.provider.provider_name,
            "model": self.provider.model_name,
            "prompt_version": self.config.prompt_version,
            "semantic_plan": (
                semantic_plan.model_dump(mode="json")
                if hasattr(semantic_plan, "model_dump")
                else semantic_plan
            )
            if semantic_plan
            else None,
            "graph_paths": graph_paths,
            "graph_context": graph_context,
        }

        eff_limit = limit or self.config.max_rows

        # 1. Schema Discovery & Tenant Boundary Check
        t_schema = time.perf_counter()
        schema_ctx = await self.schema_discovery.get_schema_context(
            datasource_id=datasource_id,
            organization_id=organization_id,
            session=session,
        )
        diagnostics["schema_discovery_ms"] = (time.perf_counter() - t_schema) * 1000
        diagnostics["tables_available"] = list(schema_ctx.allowed_tables)

        # 2. SQL Planning
        t_plan = time.perf_counter()
        plan = self.planner.plan(
            question=question,
            schema_context=schema_ctx,
            max_rows=eff_limit,
        )
        diagnostics["planning_ms"] = (time.perf_counter() - t_plan) * 1000

        # 3. SQL Generation
        t_gen = time.perf_counter()
        provider_resp = await self.provider.generate_sql(plan, schema_ctx)
        diagnostics["generation_ms"] = (time.perf_counter() - t_gen) * 1000
        diagnostics["input_tokens"] = provider_resp.input_tokens
        diagnostics["output_tokens"] = provider_resp.output_tokens

        # Estimate cost ($0.15/1M in, $0.60/1M out)
        est_cost = (provider_resp.input_tokens * 0.00000015) + (
            provider_resp.output_tokens * 0.00000060
        )
        diagnostics["cost_usd"] = round(min(est_cost, self.config.max_llm_cost_per_request), 6)

        # 4. AST Security Validation & Complexity Bounding
        t_val = time.perf_counter()
        validated_sql, complexity = self.validator.validate(
            raw_sql=provider_resp.generated_sql.sql,
            schema_context=schema_ctx,
            max_rows=eff_limit,
        )
        diagnostics["validation_ms"] = (time.perf_counter() - t_val) * 1000
        diagnostics["complexity"] = {
            "table_count": complexity.table_count,
            "join_count": complexity.join_count,
            "cte_count": complexity.cte_count,
            "subquery_count": complexity.subquery_count,
        }

        # 5. Read-Only Database Execution
        t_exec = time.perf_counter()
        query_result = await self.executor.execute(
            sql=validated_sql,
            session=session,
            max_rows=eff_limit,
        )
        diagnostics["execution_ms"] = (time.perf_counter() - t_exec) * 1000
        diagnostics["rows_returned"] = query_result.row_count
        diagnostics["truncated"] = query_result.truncated

        # 6. Python/Pandas Controlled Analysis
        analysis_result = None
        if analyze:
            t_ana = time.perf_counter()
            analysis_result = self.analyzer.analyze(query_result, question)
            diagnostics["analysis_ms"] = (time.perf_counter() - t_ana) * 1000

        # 7. Provenance & Hash Calculation
        provenance = SQLProvenanceTracker.create_provenance(
            sql=validated_sql,
            datasource_id=datasource_id,
            tables_used=provider_resp.generated_sql.tables_used,
            columns_used=provider_resp.generated_sql.columns_used,
            row_count=query_result.row_count,
            duration_ms=query_result.duration_ms,
        )

        diagnostics["total_ms"] = (time.perf_counter() - t_total_start) * 1000

        # 8. Persistence & Audit Logging
        try:
            # Add AuditLog entry
            audit_entry = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="sql_agent.query_execute",
                resource_type="data_source",
                resource_id=str(datasource_id),
                metadata_={
                    "sql_hash": provenance.sql_hash,
                    "row_count": query_result.row_count,
                    "tables_used": provenance.tables_used,
                    "duration_ms": round(diagnostics["total_ms"], 2),
                },
            )
            session.add(audit_entry)

            # Add LLMRequest entry with observability correlation
            from app.observability.context import get_current_context
            from app.observability.instrumentation.llm import get_llm_instrumentation
            from app.observability.instrumentation.sql import get_sql_instrumentation

            obs_ctx = get_current_context()
            trace_id_val = obs_ctx.trace_id if obs_ctx else None
            span_id_val = obs_ctx.span_id if obs_ctx else None
            request_id_val = obs_ctx.request_id if obs_ctx else None

            llm_entry = LLMRequest(
                organization_id=organization_id,
                user_id=user_id,
                analysis_run_id=analysis_run_id,
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                input_tokens=provider_resp.input_tokens,
                output_tokens=provider_resp.output_tokens,
                total_tokens=provider_resp.input_tokens + provider_resp.output_tokens,
                estimated_cost=Decimal(str(diagnostics["cost_usd"])),
                latency_ms=int(diagnostics["generation_ms"]),
                status="success",
                trace_id=trace_id_val,
                span_id=span_id_val,
                request_id=request_id_val,
            )
            session.add(llm_entry)

            # Record Observability Telemetry
            get_sql_instrumentation().record_query_execution(
                duration_ms=diagnostics["execution_ms"],
                rows_returned=query_result.row_count,
                status="ok",
            )
            get_llm_instrumentation().record_llm_call(
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                operation="sql_generation",
                status="ok",
                duration_ms=diagnostics["generation_ms"],
                input_tokens=provider_resp.input_tokens,
                output_tokens=provider_resp.output_tokens,
                cost_usd=float(diagnostics["cost_usd"]),
            )

            # Add UsageEvent
            usage_entry = UsageEvent(
                organization_id=organization_id,
                user_id=user_id,
                event_type="sql_agent_query",
                quantity=provider_resp.output_tokens,
                metadata_={
                    "datasource_id": str(datasource_id),
                    "sql_hash": provenance.sql_hash,
                    "row_count": query_result.row_count,
                },
            )
            session.add(usage_entry)

            # Add AnalysisSteps if attached to an AnalysisRun
            if analysis_run_id is not None:
                step_plan = AnalysisStep(
                    analysis_run_id=analysis_run_id,
                    step_type="sql_planning",
                    step_order=1,
                    status="completed",
                    input_payload={"question": question},
                    output_payload={"target_tables": plan.target_tables},
                )
                step_exec = AnalysisStep(
                    analysis_run_id=analysis_run_id,
                    step_type="sql_execution",
                    step_order=2,
                    status="completed",
                    input_payload={"sql_hash": provenance.sql_hash},
                    output_payload={"row_count": query_result.row_count},
                )
                session.add_all([step_plan, step_exec])

            await session.commit()
        except Exception as exc:
            logger.warning("Failed to persist SQL Agent audit/step telemetry (%s)", exc)
            await session.rollback()

        return SQLAgentResult(
            question=question,
            generated_sql=validated_sql,
            sql_hash=provenance.sql_hash,
            query_result=query_result,
            analysis=analysis_result,
            provenance=provenance,
            diagnostics=diagnostics,
        )
