"""Typed adapter tool wrapping ReportService."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import ReportCreateInput
from app.rbac.catalog import PERM_REPORTS_CREATE
from app.reports.service import ReportService


class ReportTool:
    """Tool compiling completed AnalysisRun into persisted executive report."""

    name: str = "report.create"
    version: str = "v1.0"
    description: str = "Generates a structured executive report from an existing AnalysisRun."
    input_schema: type[BaseModel] = ReportCreateInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_REPORTS_CREATE
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE_WRITE
    supports_preview: bool = True
    supports_approval: bool = True
    idempotent: bool = False

    def __init__(self, report_service: ReportService | None = None) -> None:
        self.report_service = report_service or ReportService()

    async def validate(self, tool_input: dict[str, Any]) -> ReportCreateInput:
        try:
            return ReportCreateInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, ReportCreateInput)
            else ReportCreateInput.model_validate(validated_input)
        )
        return {
            "action": "create_report_from_analysis",
            "analysis_run_id": str(inp.analysis_run_id),
            "title": inp.title,
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, ReportCreateInput)
            else ReportCreateInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()

        report, report_version, doc = await self.report_service.create_report_from_analysis(
            session=context.db_session,
            organization_id=context.organization_id,
            analysis_run_id=inp.analysis_run_id,
            title=inp.title,
            user_id=context.user_id,
            subtitle=inp.subtitle,
            template=inp.template,
        )

        duration_ms = (time.perf_counter() - t_start) * 1000

        evidence_items = [
            {
                "evidence_id": f"REP-{str(report.id)[:8]}",
                "source_type": "report",
                "content": doc.executive_summary or inp.title,
                "metadata": {"report_id": str(report.id), "version_id": str(report_version.id)},
            }
        ]

        return ToolOutput(
            success=True,
            data={
                "report_id": str(report.id),
                "version_id": str(report_version.id),
                "title": report.title,
                "status": report.status,
            },
            evidence_items=evidence_items,
            tokens_used=100,
            cost_usd=0.001,
            duration_ms=duration_ms,
        )
