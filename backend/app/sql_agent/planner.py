"""SQL query planning, table linking, and analytical intent framing."""

import re
from dataclasses import dataclass

from app.sql_agent.models import SchemaContext


@dataclass(frozen=True)
class SQLPlan:
    """Structured execution plan for translating natural language questions into safe SQL."""

    question: str
    target_tables: list[str]
    suggested_aggregations: list[str]
    filter_hints: list[str]
    max_limit: int
    dialect: str = "postgres"


class SQLPlanner:
    """Extracts schema intent and formulates targeted constraints for SQL generation."""

    def plan(self, question: str, schema_context: SchemaContext, max_rows: int = 1000) -> SQLPlan:
        """Formulate a targeted SQL plan mapping question terms to verified schema elements."""
        q_lower = question.lower()
        matched_tables: list[str] = []

        # 1. Match table names against schema
        for tbl_name in schema_context.allowed_tables:
            # Check if table name or singular/plural version appears in question
            base_name = tbl_name.rstrip("s")
            if tbl_name in q_lower or (len(base_name) > 3 and base_name in q_lower):
                matched_tables.append(tbl_name)

        # Fallback to all tables if no explicit match (or first available table)
        if not matched_tables:
            matched_tables = list(schema_context.allowed_tables)

        # 2. Identify analytical aggregation intents
        suggested_aggs: list[str] = []
        sum_terms = ["total", "sum", "overall", "مجموع", "إجمالي", "toplam"]
        if any(term in q_lower for term in sum_terms):
            suggested_aggs.append("SUM")
        if any(term in q_lower for term in ["average", "avg", "mean", "متوسط", "معدل", "ortalama"]):
            suggested_aggs.append("AVG")
        if any(term in q_lower for term in ["count", "how many", "number of", "عدد", "kaç tane"]):
            suggested_aggs.append("COUNT")
        if any(term in q_lower for term in ["minimum", "min", "lowest", "أدنى", "en düşük"]):
            suggested_aggs.append("MIN")
        if any(term in q_lower for term in ["maximum", "max", "highest", "أعلى", "en yüksek"]):
            suggested_aggs.append("MAX")

        # 3. Extract temporal / filter hints
        filter_hints: list[str] = []
        # Match years (e.g. 2024, 2025, 2026)
        year_match = re.findall(r"\b(20\d{2})\b", question)
        for y in year_match:
            filter_hints.append(f"year={y}")

        # Match quarters (e.g. Q1, Q2, Q3, Q4)
        qtr_match = re.findall(r"\b[Qq]([1-4])\b", question)
        for q in qtr_match:
            filter_hints.append(f"quarter=Q{q}")

        return SQLPlan(
            question=question,
            target_tables=matched_tables,
            suggested_aggregations=suggested_aggs,
            filter_hints=filter_hints,
            max_limit=max_rows,
            dialect=schema_context.dialect,
        )
