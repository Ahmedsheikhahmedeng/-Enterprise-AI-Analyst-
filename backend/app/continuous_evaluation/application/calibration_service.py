"""Confidence calibration service calculating Expected Calibration Error, Brier Score, and reliability curves."""

import uuid

from app.continuous_evaluation.domain.models import CalibrationAnalysis, CalibrationBucket
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol
from app.observability.instrumentation.continuous_evaluation import (
    ContinuousEvaluationInstrumentation,
)


class CalibrationService:
    """Computes calibration metrics across confidence buckets for evaluation runs."""

    def __init__(
        self,
        repository: ContinuousEvaluationRepositoryProtocol,
        instrumentation: ContinuousEvaluationInstrumentation | None = None,
    ) -> None:
        self.repository = repository
        self.instrumentation = instrumentation

    def compute_calibration(
        self,
        run_id: uuid.UUID,
        predictions: list[tuple[float, bool]],  # list of (confidence [0.0, 1.0], is_correct)
        num_buckets: int = 10,
    ) -> CalibrationAnalysis:
        """Calculates ECE (Expected Calibration Error), Brier Score, and reliability diagram bins."""
        if not predictions:
            return CalibrationAnalysis(run_id=run_id, ece=0.0, brier_score=0.0, buckets=[])

        total_samples = len(predictions)
        bucket_size = 1.0 / num_buckets

        # Initialize buckets
        raw_buckets: list[list[tuple[float, bool]]] = [[] for _ in range(num_buckets)]

        # Calculate Brier score: (1/N) * sum((prob - label)^2)
        squared_errors = []
        for conf, correct in predictions:
            # Bound confidence between 0.0 and 1.0
            bounded_conf = max(0.0, min(1.0, conf))
            target_val = 1.0 if correct else 0.0
            squared_errors.append((bounded_conf - target_val) ** 2)

            b_idx = min(int(bounded_conf / bucket_size), num_buckets - 1)
            raw_buckets[b_idx].append((bounded_conf, correct))

        brier_score = sum(squared_errors) / total_samples

        # Calculate ECE: sum_m (|B_m| / N) * |acc(B_m) - conf(B_m)|
        ece = 0.0
        calibration_buckets: list[CalibrationBucket] = []

        for idx, b_samples in enumerate(raw_buckets):
            b_start = idx * bucket_size
            b_end = (idx + 1) * bucket_size

            if not b_samples:
                calibration_buckets.append(
                    CalibrationBucket(
                        bin_start=b_start,
                        bin_end=b_end,
                        avg_confidence=(b_start + b_end) / 2.0,
                        accuracy=0.0,
                        sample_count=0,
                    )
                )
                continue

            count = len(b_samples)
            avg_conf = sum(p[0] for p in b_samples) / count
            accuracy = sum(1 for p in b_samples if p[1]) / count

            ece += (count / total_samples) * abs(accuracy - avg_conf)

            calibration_buckets.append(
                CalibrationBucket(
                    bin_start=b_start,
                    bin_end=b_end,
                    avg_confidence=avg_conf,
                    accuracy=accuracy,
                    sample_count=count,
                )
            )

        analysis = CalibrationAnalysis(
            run_id=run_id,
            ece=round(ece, 4),
            brier_score=round(brier_score, 4),
            buckets=calibration_buckets,
        )

        return analysis

    async def record_and_track_calibration(
        self,
        analysis: CalibrationAnalysis,
        organization_id: uuid.UUID,
    ) -> None:
        """Persists calibration results and records telemetry."""
        await self.repository.record_calibration(analysis, organization_id)
        if self.instrumentation:
            self.instrumentation.record_calibration("end_to_end", analysis.ece)

    async def get_calibration(
        self,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> CalibrationAnalysis | None:
        """Retrieves stored calibration analysis."""
        return await self.repository.get_calibration(run_id, organization_id)
