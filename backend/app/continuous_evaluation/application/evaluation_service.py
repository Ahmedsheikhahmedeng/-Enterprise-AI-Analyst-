"""Continuous evaluation service coordinating benchmark executions, slices, versions, and scorecards."""

import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.service import AIAnalystService
from app.continuous_evaluation.application.metric_registry import MetricRegistry
from app.continuous_evaluation.domain.models import Benchmark, SystemVersionInfo
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol
from app.evaluation.benchmark import BenchmarkRunner
from app.evaluation.config import EvaluationConfig, get_evaluation_config
from app.evaluation.scorecard import ScorecardGenerator
from app.models.audit import AuditLog
from app.models.evaluation import EvaluationCaseResult
from app.observability.instrumentation.continuous_evaluation import (
    ContinuousEvaluationInstrumentation,
)

logger = logging.getLogger(__name__)


class ContinuousEvaluationService:
    """Enterprise evaluation engine extending Task 20 with continuous slices, versions, and composite scorecards."""

    def __init__(
        self,
        repository: ContinuousEvaluationRepositoryProtocol,
        metric_registry: MetricRegistry | None = None,
        config: EvaluationConfig | None = None,
        benchmark_runner: BenchmarkRunner | None = None,
        scorecard_generator: ScorecardGenerator | None = None,
        instrumentation: ContinuousEvaluationInstrumentation | None = None,
    ) -> None:
        self.repository = repository
        self.metric_registry = metric_registry or MetricRegistry()
        self.config = config or get_evaluation_config()
        self.benchmark_runner = benchmark_runner or BenchmarkRunner(self.config)
        self.scorecard_generator = scorecard_generator or ScorecardGenerator(self.config)
        self.instrumentation = instrumentation

    async def execute_benchmark(
        self,
        session: AsyncSession,
        *,
        benchmark: Benchmark,
        analyst_service: AIAnalystService,
        version_info: SystemVersionInfo | None = None,
        max_cases: int | None = None,
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Executes benchmark run, produces granular scorecards, slices, and records version metadata."""
        v_info = version_info or SystemVersionInfo()

        # Emit audit start
        if self.instrumentation:
            self.instrumentation.record_run_started(benchmark.task_type, benchmark.target.value)

        try:
            run, results = await self.benchmark_runner.run_benchmark(
                session=session,
                analyst_service=analyst_service,
                organization_id=benchmark.organization_id,
                dataset_id=benchmark.dataset_id,
                dataset_version=int(v_info.dataset_version)
                if v_info.dataset_version.isdigit()
                else None,
                max_cases=max_cases,
                user_id=user_id,
            )

            # Check for partial failure
            is_partial = False
            failed_case_count = sum(1 for r in results if not r.passed)
            if failed_case_count > 0 and failed_case_count < len(results):
                is_partial = True

            # Standard Task 20 scorecard
            base_scorecard = self.scorecard_generator.generate(
                run_id=run.id,
                dataset_id=run.dataset_id,
                dataset_version=run.dataset_version,
                results=results,
            )

            # Slice evaluations
            slice_analytics = self.compute_slices(results)

            # Route quality analytics
            route_analytics = self.compute_route_quality(results)

            # Composite quality score
            metrics_map = base_scorecard.to_dict()["metrics"]
            metrics_map.update(route_analytics)
            composite_quality = self.metric_registry.compute_composite_score(metrics_map)

            # Generate config & version hash
            config_hash = self._generate_config_hash(v_info, benchmark)

            extended_scorecard = {
                "benchmark_id": str(benchmark.id),
                "run_id": str(run.id),
                "target": benchmark.target.value,
                "status": "PARTIAL"
                if is_partial
                else ("COMPLETED" if run.status == "completed" else run.status),
                "version_info": v_info.to_dict(),
                "config_hash": config_hash,
                "base_scorecard": base_scorecard.to_dict(),
                "composite_quality": composite_quality.to_dict(),
                "slice_analytics": slice_analytics,
                "route_analytics": route_analytics,
            }

            if self.instrumentation:
                self.instrumentation.record_run_completed(
                    evaluation_type=benchmark.task_type,
                    target=benchmark.target.value,
                    status="completed",
                    duration_seconds=(run.duration_ms or 0) / 1000.0,
                    score=composite_quality.overall_score,
                )

            # Audit record
            audit = AuditLog(
                organization_id=benchmark.organization_id,
                user_id=user_id,
                action="continuous_evaluation.run_completed",
                resource_type="continuous_evaluation_run",
                resource_id=str(run.id),
                metadata_={
                    "benchmark_id": str(benchmark.id),
                    "overall_score": composite_quality.overall_score,
                    "target": benchmark.target.value,
                    "is_partial": is_partial,
                },
            )
            session.add(audit)
            await session.commit()

            return extended_scorecard

        except Exception as exc:
            logger.exception("Continuous evaluation benchmark failed: %s", exc)
            if self.instrumentation:
                self.instrumentation.record_run_completed(
                    evaluation_type=benchmark.task_type,
                    target=benchmark.target.value,
                    status="failed",
                    duration_seconds=0.0,
                    score=0.0,
                )
            raise

    def compute_slices(self, results: list[EvaluationCaseResult]) -> dict[str, Any]:
        """Calculates performance breakdowns across difficulty, language, and route slices."""
        if not results:
            return {"by_difficulty": {}, "by_language": {}, "by_route": {}}

        diff_counts: dict[str, dict[str, int]] = {}
        lang_counts: dict[str, dict[str, int]] = {}
        route_counts: dict[str, dict[str, int]] = {}

        for r in results:
            # Case difficulty
            diff = getattr(r.case, "difficulty", "medium").upper()
            diff_counts.setdefault(diff, {"total": 0, "passed": 0})
            diff_counts[diff]["total"] += 1
            if r.passed:
                diff_counts[diff]["passed"] += 1

            # Language
            lang = getattr(r.case, "language", "en").lower()
            lang_counts.setdefault(lang, {"total": 0, "passed": 0})
            lang_counts[lang]["total"] += 1
            if r.passed:
                lang_counts[lang]["passed"] += 1

            # Route
            route = getattr(r.case, "route_expected", "none").upper()
            route_counts.setdefault(route, {"total": 0, "passed": 0})
            route_counts[route]["total"] += 1
            if r.passed:
                route_counts[route]["passed"] += 1

        def _calc_rates(counts: dict[str, dict[str, int]]) -> dict[str, float]:
            return {
                k: round(v["passed"] / v["total"], 4) if v["total"] > 0 else 0.0
                for k, v in counts.items()
            }

        return {
            "by_difficulty": _calc_rates(diff_counts),
            "by_language": _calc_rates(lang_counts),
            "by_route": _calc_rates(route_counts),
        }

    def compute_route_quality(self, results: list[EvaluationCaseResult]) -> dict[str, float]:
        """Measures specific routing precision across RAG, SQL, GRAPH, and HYBRID targets."""
        if not results:
            return {"route_accuracy": 1.0}

        total_routes = len(results)
        matching_routes = 0

        route_specific: dict[str, dict[str, int]] = {
            "RAG": {"total": 0, "correct": 0},
            "SQL": {"total": 0, "correct": 0},
            "GRAPH": {"total": 0, "correct": 0},
            "HYBRID": {"total": 0, "correct": 0},
            "NONE": {"total": 0, "correct": 0},
        }

        for r in results:
            expected = getattr(r.case, "route_expected", "none").upper()
            actual = (r.actual_route or "none").upper()
            is_match = expected == actual

            if is_match:
                matching_routes += 1

            if expected in route_specific:
                route_specific[expected]["total"] += 1
                if is_match:
                    route_specific[expected]["correct"] += 1

        analytics: dict[str, float] = {
            "route_accuracy": round(matching_routes / total_routes, 4) if total_routes > 0 else 1.0
        }
        for rt, vals in route_specific.items():
            key = f"{rt.lower()}_route_accuracy"
            analytics[key] = round(vals["correct"] / vals["total"], 4) if vals["total"] > 0 else 1.0

        return analytics

    def _generate_config_hash(self, version_info: SystemVersionInfo, benchmark: Benchmark) -> str:
        """Produces deterministic SHA-256 fingerprint for run reproducibility."""
        payload = {
            "benchmark_id": str(benchmark.id),
            "version_info": version_info.to_dict(),
            "weights": self.metric_registry.get_category_weights(),
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
