"""Stage Progress & Weighted Progress Calculator — TASK 34.

Provides deterministic, weighted progress tracking across reasoning stages:
UNDERSTANDING    10%
SEMANTIC         10%
GRAPH            10%
PLANNING         10%
EXECUTION        30%
EVIDENCE         10%
VERIFICATION     10%
RESPONSE         10%
Total:          100%
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.api.v1.platform.schemas.execution import StageProgress


@dataclass
class StageWeightConfig:
    """Configurable weights assigned to discrete stages of the enterprise reasoning pipeline."""

    weights: dict[str, int] = field(
        default_factory=lambda: {
            "UNDERSTANDING": 10,
            "SEMANTIC": 10,
            "GRAPH": 10,
            "PLANNING": 10,
            "EXECUTION": 30,
            "EVIDENCE": 10,
            "VERIFICATION": 10,
            "RESPONSE": 10,
        }
    )

    stage_order: list[str] = field(
        default_factory=lambda: [
            "UNDERSTANDING",
            "SEMANTIC",
            "GRAPH",
            "PLANNING",
            "EXECUTION",
            "EVIDENCE",
            "VERIFICATION",
            "RESPONSE",
        ]
    )


class ProgressTracker:
    """Calculates weighted cumulative progress and stage status transitions."""

    def __init__(self, config: StageWeightConfig | None = None) -> None:
        self.config = config or StageWeightConfig()
        self._completed_stages: set[str] = set()
        self._current_stage: str | None = None
        self._stage_timestamps: dict[str, dict[str, str]] = {}

    def start_stage(self, stage: str) -> StageProgress:
        """Mark a stage as running and return stage progress status."""
        stage_norm = stage.upper()
        self._current_stage = stage_norm
        now_str = datetime.now(UTC).isoformat()
        if stage_norm not in self._stage_timestamps:
            self._stage_timestamps[stage_norm] = {"started_at": now_str}
        else:
            self._stage_timestamps[stage_norm]["started_at"] = now_str

        progress = self._compute_progress(in_progress_stage=stage_norm)
        return StageProgress(
            stage=stage_norm,
            status="RUNNING",
            progress=progress,
            started_at=now_str,
        )

    def complete_stage(self, stage: str) -> StageProgress:
        """Mark a stage as completed and increment cumulative progress."""
        stage_norm = stage.upper()
        self._completed_stages.add(stage_norm)
        now_str = datetime.now(UTC).isoformat()
        if stage_norm not in self._stage_timestamps:
            self._stage_timestamps[stage_norm] = {
                "started_at": now_str,
                "completed_at": now_str,
            }
        else:
            self._stage_timestamps[stage_norm]["completed_at"] = now_str

        progress = self._compute_progress()
        return StageProgress(
            stage=stage_norm,
            status="COMPLETED",
            progress=progress,
            started_at=self._stage_timestamps[stage_norm].get("started_at"),
            completed_at=now_str,
        )

    def fail_stage(self, stage: str) -> StageProgress:
        """Mark a stage as failed."""
        stage_norm = stage.upper()
        now_str = datetime.now(UTC).isoformat()
        return StageProgress(
            stage=stage_norm,
            status="FAILED",
            progress=self._compute_progress(),
            started_at=self._stage_timestamps.get(stage_norm, {}).get("started_at"),
            completed_at=now_str,
        )

    def get_progress(self) -> int:
        """Current total weighted progress percentage (0 - 100)."""
        return self._compute_progress(in_progress_stage=self._current_stage)

    def _compute_progress(self, in_progress_stage: str | None = None) -> int:
        """Calculate weighted percentage from completed and active stages."""
        total = 0
        for stage in self.config.stage_order:
            weight = self.config.weights.get(stage, 0)
            if stage in self._completed_stages:
                total += weight
            elif stage == in_progress_stage:
                # Active stage contributes half its weight until completed
                total += weight // 2

        return min(100, max(0, total))

    def export_summary(self) -> list[dict[str, Any]]:
        """Export all recorded stages with their completion times and statuses."""
        summary = []
        for stage in self.config.stage_order:
            status = "PENDING"
            if stage in self._completed_stages:
                status = "COMPLETED"
            elif stage == self._current_stage:
                status = "RUNNING"

            ts = self._stage_timestamps.get(stage, {})
            summary.append(
                {
                    "stage": stage,
                    "status": status,
                    "weight": self.config.weights.get(stage, 0),
                    "started_at": ts.get("started_at"),
                    "completed_at": ts.get("completed_at"),
                }
            )
        return summary
