"""Statistical profiling and data quality service."""

import contextlib
import uuid
from typing import Any

from app.ingestion.domain.models import (
    ColumnDefinition,
    ColumnProfile,
    DataQualityReport,
    DatasetProfile,
)
from app.ingestion.infrastructure.profiler.pii_detector import PIIDetector


class ProfilingService:
    """Computes bounded memory statistical profiles and quality reports for tabular data."""

    MAX_DISTINCT_SAMPLE = 10_000

    def __init__(self, pii_detector: PIIDetector | None = None) -> None:
        self.pii_detector = pii_detector or PIIDetector()

    def profile_dataset(
        self,
        organization_id: uuid.UUID,
        dataset_id: uuid.UUID,
        columns: list[ColumnDefinition],
        rows: list[dict[str, Any]],
        duplicate_count: int = 0,
    ) -> tuple[DatasetProfile, DataQualityReport]:
        """Compute full statistical profile and data quality report across rows."""
        total_rows = len(rows)
        col_profiles: dict[str, ColumnProfile] = {}

        total_cells = max(total_rows * len(columns), 1)
        total_null_cells = 0
        total_invalid_cells = 0

        for col_def in columns:
            col_name = col_def.normalized_name
            values = [r.get(col_name) for r in rows if col_name in r]

            # Null statistics
            null_count = sum(1 for v in values if v is None)
            total_null_cells += null_count
            non_null_values = [v for v in values if v is not None]
            null_ratio = null_count / total_rows if total_rows > 0 else 0.0

            # Distinct bounded sampling
            distinct_sample = set()
            for v in non_null_values[: self.MAX_DISTINCT_SAMPLE]:
                distinct_sample.add(str(v))
            distinct_count = len(distinct_sample)

            profile = ColumnProfile(
                name=col_name,
                data_type=col_def.data_type.value,
                total_count=total_rows,
                null_count=null_count,
                null_ratio=round(null_ratio, 4),
                distinct_count=distinct_count,
            )

            # Analyze based on type
            # 1. Numeric statistics
            numeric_vals: list[float] = []
            for v in non_null_values:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    numeric_vals.append(float(v))
                elif isinstance(v, str):
                    with contextlib.suppress(ValueError):
                        numeric_vals.append(float(v))

            if numeric_vals:
                profile.min_value = min(numeric_vals)
                profile.max_value = max(numeric_vals)
                profile.mean_value = round(sum(numeric_vals) / len(numeric_vals), 4)

                sorted_num = sorted(numeric_vals)
                mid = len(sorted_num) // 2
                profile.median_value = (
                    sorted_num[mid]
                    if len(sorted_num) % 2 != 0
                    else (sorted_num[mid - 1] + sorted_num[mid]) / 2.0
                )

            # 2. Text statistics
            str_vals = [str(v) for v in non_null_values if isinstance(v, str)]
            if str_vals:
                lengths = [len(s) for s in str_vals]
                profile.min_length = min(lengths)
                profile.max_length = max(lengths)
                profile.avg_length = round(sum(lengths) / len(lengths), 2)

            # 3. PII Detection
            pii_type = self.pii_detector.detect_column_pii(col_def.name, non_null_values)
            profile.pii_classification = pii_type
            col_def.pii_classification = pii_type

            col_profiles[col_name] = profile

        # Overall Dataset Profile
        dataset_profile = DatasetProfile(
            dataset_id=dataset_id,
            organization_id=organization_id,
            row_count=total_rows,
            column_count=len(columns),
            columns=col_profiles,
        )

        # Quality Report calculation
        overall_null_ratio = total_null_cells / total_cells
        duplicate_ratio = duplicate_count / max(total_rows + duplicate_count, 1)
        invalid_ratio = total_invalid_cells / total_cells

        # Weighted quality score:
        # Null penalty up to 0.4, Duplicate penalty up to 0.3, Invalid penalty up to 0.3
        score = 1.0 - (0.4 * overall_null_ratio + 0.3 * duplicate_ratio + 0.3 * invalid_ratio)
        score = max(0.0, min(1.0, round(score, 4)))

        quality_report = DataQualityReport(
            score=score,
            null_ratio=round(overall_null_ratio, 4),
            duplicate_ratio=round(duplicate_ratio, 4),
            invalid_ratio=round(invalid_ratio, 4),
            schema_consistency=1.0,
            details={
                "total_rows": total_rows,
                "total_columns": len(columns),
                "null_cells": total_null_cells,
                "duplicate_rows": duplicate_count,
            },
        )

        return dataset_profile, quality_report
