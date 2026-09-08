"""Typed adapter tool wrapping BenchmarkRunner."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import EvaluationRunInput
from app.analyst.service import AIAnalystService
from app.evaluation.benchmark import BenchmarkRunner
from app.rbac.catalog import PERM_EVALUATION_RUN


class EvaluationTool:
    """Tool running evaluation benchmarks on historical datasets without modifying them."""

    name: str = "evaluation.run"
    version: str = "v1.0"
    description: str = "Runs automated benchmark evaluation on a specified dataset."
    input_schema: type[BaseModel] = EvaluationRunInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_EVALUATION_RUN
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = True
    idempotent: bool = True

    def __init__(
        self,
        runner: BenchmarkRunner | None = None,
        analyst_service: AIAnalystService | None = None,
    ) -> None:
        self.runner = runner or BenchmarkRunner()
        self.analyst_service = analyst_service or AIAnalystService()

    async def validate(self, tool_input: dict[str, Any]) -> EvaluationRunInput:
        try:
            return EvaluationRunInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, EvaluationRunInput)
            else EvaluationRunInput.model_validate(validated_input)
        )
        return {
            "action": "run_benchmark_evaluation",
            "dataset_id": str(inp.dataset_id),
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, EvaluationRunInput)
            else EvaluationRunInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()

        run, case_results = await self.runner.run_benchmark(
            session=context.db_session,
            analyst_service=self.analyst_service,
            organization_id=context.organization_id,
            dataset_id=inp.dataset_id,
            dataset_version=inp.dataset_version,
            max_cases=inp.max_cases,
            tags=inp.tags,
            user_id=context.user_id,
        )

        duration_ms = (time.perf_counter() - t_start) * 1000
        accuracy = round(run.passed_cases / run.total_cases, 4) if run.total_cases > 0 else 1.0
        hallucination_rate = (
            round(run.failed_cases / run.total_cases, 4) if run.total_cases > 0 else 0.0
        )

        evidence_items = [
            {
                "evidence_id": f"EVAL-{str(run.id)[:8]}",
                "source_type": "evaluation",
                "content": f"EvaluationRun score: accuracy={accuracy}, passed={run.passed_cases}/{run.total_cases}",
                "metadata": {
                    "run_id": str(run.id),
                    "total_cases": run.total_cases,
                    "passed_cases": run.passed_cases,
                },
            }
        ]

        return ToolOutput(
            success=run.status in ("completed", "finished", "passed"),
            data={
                "run_id": str(run.id),
                "accuracy_score": accuracy,
                "hallucination_rate": hallucination_rate,
                "total_cases": run.total_cases,
                "passed_cases": run.passed_cases,
                "failed_cases": run.failed_cases,
            },
            evidence_items=evidence_items,
            tokens_used=500,
            cost_usd=0.005,
            duration_ms=duration_ms,
        )
