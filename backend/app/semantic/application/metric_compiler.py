"""Metric SQL Compiler translating high-level semantic expressions into safe SQL fragments."""

import re

from app.semantic.domain.errors import InvalidMetricFormulaError

# Dangerous SQL patterns strictly forbidden in metric expressions
DANGEROUS_SQL_PATTERNS = re.compile(
    r"(;|--|/\*|\*/|\b(drop|truncate|delete|insert|update|alter|create|exec|execute|union|into|load_file|system)\b)",
    re.IGNORECASE,
)

# Allowed aggregation keywords
ALLOWED_AGGREGATIONS = {"SUM", "COUNT", "AVG", "MIN", "MAX", "MEDIAN", "COUNT_DISTINCT"}


class MetricCompiler:
    """Compiles validated semantic metric formulas into secure SQL expressions."""

    @classmethod
    def validate_formula(cls, formula: str) -> None:
        """Verify that a metric formula does not attempt SQL injection or dangerous operations."""
        cleaned = formula.strip()
        if not cleaned:
            raise InvalidMetricFormulaError(formula, "Formula expression cannot be empty.")

        if DANGEROUS_SQL_PATTERNS.search(cleaned):
            raise InvalidMetricFormulaError(
                formula,
                "Formula contains prohibited SQL statements, comments, or commands.",
            )

        # Basic balanced parenthesis check
        if cleaned.count("(") != cleaned.count(")"):
            raise InvalidMetricFormulaError(
                formula, "Unbalanced parentheses in formula expression."
            )

    @classmethod
    def compile_metric(
        cls,
        metric_name: str,
        formula: str,
        aggregation: str,
        table_name: str,
        column_mapping: dict[str, str],
        filters: list[str] | None = None,
    ) -> str:
        """Compile formula into a safe SELECT SQL query string.

        Args:
            metric_name: Identifier for the output metric alias.
            formula: Mathematical or aggregation formula, e.g. 'SUM(orders.total_amount)'.
            aggregation: Declared aggregation (SUM, AVG, COUNT, etc.).
            table_name: Validated target database table.
            column_mapping: Map from semantic/logical column names to physical column names.
            filters: Additional semantic filter clauses to append.

        Returns:
            Rendered read-only SQL SELECT query snippet.
        """
        cls.validate_formula(formula)

        # Replace logical column references with validated physical columns
        rendered_expr = formula
        for logical_col, physical_col in column_mapping.items():
            pattern = re.compile(rf"\b{re.escape(logical_col)}\b", re.IGNORECASE)
            rendered_expr = pattern.sub(f'"{physical_col}"', rendered_expr)

        where_clause = ""
        if filters:
            for f in filters:
                cls.validate_formula(f)
            where_clause = " WHERE " + " AND ".join(filters)

        sql = f'SELECT {rendered_expr} AS "{metric_name}" FROM "{table_name}"{where_clause}'
        return sql
