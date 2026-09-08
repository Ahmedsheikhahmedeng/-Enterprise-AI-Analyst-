"""Controlled Python and Pandas data analysis layer for SQL results without LLM arithmetic."""

from decimal import Decimal
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from app.core.logging import get_logger
from app.sql_agent.models import SQLQueryResult, StructuredAnalysisResult

logger = get_logger("sql_agent.analyzer")


class SQLResultAnalyzer:
    """Executes safe, deterministic mathematical aggregations and trends on SQL tabular results."""

    def analyze(self, query_result: SQLQueryResult, question: str) -> StructuredAnalysisResult:
        """Perform statistical aggregations, relative growth, and summaries without eval/exec."""
        if not query_result.rows:
            return StructuredAnalysisResult(
                summary="The query executed successfully but returned 0 rows.",
                metrics={"row_count": 0},
            )

        df = pd.DataFrame(query_result.rows)
        metrics: dict[str, Any] = {"row_count": query_result.row_count}
        comparisons: list[dict[str, Any]] = []
        trends: list[dict[str, Any]] = []

        # Identify numeric columns for aggregations
        numeric_cols: list[str] = []
        for col in df.columns:
            # Check if column values can be parsed as numeric
            try:
                coerced = pd.to_numeric(df[col], errors="coerce")
                if coerced.notna().sum() > 0:
                    df[f"__num_{col}"] = coerced
                    numeric_cols.append(col)
            except Exception:
                continue

        # Compute key descriptive aggregates
        summary_points: list[str] = [
            f"Query returned {query_result.row_count} record(s) "
            f"across {len(query_result.columns)} column(s)."
        ]

        for col in numeric_cols:
            num_series = df[f"__num_{col}"].dropna()
            if num_series.empty:
                continue

            col_sum = num_series.sum()
            col_mean = num_series.mean()
            col_min = num_series.min()
            col_max = num_series.max()

            # Preserve formatting
            metrics[f"{col}_sum"] = round(float(col_sum), 2)
            metrics[f"{col}_avg"] = round(float(col_mean), 2)
            metrics[f"{col}_min"] = round(float(col_min), 2)
            metrics[f"{col}_max"] = round(float(col_max), 2)

            summary_points.append(
                f"For '{col}': Total is {col_sum:,.2f}, Average is {col_mean:,.2f} "
                f"(Min: {col_min:,.2f}, Max: {col_max:,.2f})."
            )

            # Compute percentage change across rows if more than 1 record
            if len(num_series) > 1:
                first_val = num_series.iloc[0]
                last_val = num_series.iloc[-1]

                overall_pct = self.calculate_percent_change(first_val, last_val)
                if overall_pct is not None:
                    direction = "increased" if overall_pct > 0 else "decreased"
                    comparisons.append(
                        {
                            "metric": col,
                            "first_value": round(float(first_val), 2),
                            "last_value": round(float(last_val), 2),
                            "percent_change": round(float(overall_pct), 2),
                            "direction": direction,
                        }
                    )
                    trends.append(
                        {
                            "metric": col,
                            "trend": (
                                f"{direction.capitalize()} by {abs(overall_pct):.2f}% "
                                "from start to end of sequence."
                            ),
                        }
                    )

        summary_text = " ".join(summary_points)

        return StructuredAnalysisResult(
            summary=summary_text,
            metrics=metrics,
            comparisons=comparisons,
            trends=trends,
        )

    @staticmethod
    def calculate_percent_change(
        old_val: float | int | Decimal | None,
        new_val: float | int | Decimal | None,
    ) -> float | None:
        """Safely calculate percentage change: (new - old) / old * 100 handling zero and nulls."""
        if old_val is None or new_val is None:
            return None
        try:
            old_f = float(old_val)
            new_f = float(new_val)
            if old_f == 0.0:
                return None
            return ((new_f - old_f) / abs(old_f)) * 100.0
        except (ZeroDivisionError, ValueError, OverflowError):
            return None
