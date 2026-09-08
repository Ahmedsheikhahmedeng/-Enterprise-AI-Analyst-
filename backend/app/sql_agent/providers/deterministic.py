"""Deterministic offline SQL generation provider for predictable CI and test suite execution."""

import time

from app.sql_agent.models import GeneratedSQL, SchemaContext
from app.sql_agent.planner import SQLPlan
from app.sql_agent.providers.base import SQLProviderResponse


class DeterministicSQLProvider:
    """Offline, deterministic generator translating known analytical intents to valid SQL."""

    def __init__(self, model_name: str = "deterministic-sql-v1") -> None:
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "deterministic"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_sql(
        self,
        plan: SQLPlan,
        schema_context: SchemaContext,
    ) -> SQLProviderResponse:
        """Generate deterministic SQL based on question intent and available schema tables."""
        t0 = time.perf_counter()
        q = plan.question.lower()

        # 1. Security test cases: if the test specifically asks to test forbidden operations
        if "delete from" in q:
            target_tbl = plan.target_tables[0] if plan.target_tables else "sales"
            sql = f"DELETE FROM {target_tbl};"
            tables = [target_tbl]
            cols = ["*"]
        elif "drop table" in q:
            target_tbl = plan.target_tables[0] if plan.target_tables else "sales"
            sql = f"DROP TABLE {target_tbl};"
            tables = [target_tbl]
            cols = []
        elif "insert into" in q:
            target_tbl = plan.target_tables[0] if plan.target_tables else "sales"
            sql = f"INSERT INTO {target_tbl} (id) VALUES (1);"
            tables = [target_tbl]
            cols = ["id"]
        elif "multiple statements" in q or "drop" in q and ";" in q:
            target_tbl = plan.target_tables[0] if plan.target_tables else "sales"
            sql = f"SELECT * FROM {target_tbl}; DROP TABLE customers;"
            tables = [target_tbl, "customers"]
            cols = ["*"]

        # 2. Analytical test cases
        elif "revenue by quarter" in q or ("quarter" in q and "revenue" in q):
            target_tbl = (
                "sales"
                if "sales" in schema_context.allowed_tables
                else (plan.target_tables[0] if plan.target_tables else "sales")
            )
            where_clause = " WHERE year = 2025" if "2025" in q else ""
            sql = (
                f"SELECT quarter, SUM(revenue) AS total_revenue "
                f"FROM {target_tbl}{where_clause} "
                f"GROUP BY quarter ORDER BY quarter"
            )
            tables = [target_tbl]
            cols = ["quarter", "revenue"]

        elif (
            "customer" in q
            and "order" in q
            and "orders" in schema_context.allowed_tables
            and "customers" in schema_context.allowed_tables
        ):
            # Join query test case
            sql = (
                "SELECT c.name, COUNT(o.id) AS order_count, SUM(o.amount) AS total_spent "
                "FROM customers c JOIN orders o ON c.id = o.customer_id "
                "GROUP BY c.name ORDER BY total_spent DESC"
            )
            tables = ["customers", "orders"]
            cols = ["name", "id", "amount", "customer_id"]

        elif "average" in q or "avg" in q:
            target_tbl = (
                plan.target_tables[0]
                if plan.target_tables
                else list(schema_context.allowed_tables)[0]
            )
            allowed_cols = schema_context.allowed_columns.get(target_tbl, set())
            num_col = "amount" if "amount" in allowed_cols else "revenue"
            sql = f"SELECT AVG({num_col}) AS avg_value FROM {target_tbl}"
            tables = [target_tbl]
            cols = [num_col]

        elif "total" in q or "sum" in q:
            target_tbl = (
                plan.target_tables[0]
                if plan.target_tables
                else list(schema_context.allowed_tables)[0]
            )
            allowed_cols = schema_context.allowed_columns.get(target_tbl, set())
            num_col = "amount" if "amount" in allowed_cols else "revenue"
            sql = f"SELECT SUM({num_col}) AS total_value FROM {target_tbl}"
            tables = [target_tbl]
            cols = [num_col]

        else:
            # Fallback safe select
            target_tbl = (
                plan.target_tables[0]
                if plan.target_tables
                else (
                    list(schema_context.allowed_tables)[0]
                    if schema_context.allowed_tables
                    else "sales"
                )
            )
            sql = f"SELECT * FROM {target_tbl}"
            tables = [target_tbl]
            cols = ["*"]

        latency = (time.perf_counter() - t0) * 1000

        gen_sql = GeneratedSQL(
            sql=sql,
            dialect=schema_context.dialect,
            tables_used=tables,
            columns_used=cols,
            confidence=0.98,
            explanation=f"Generated deterministic SQL for query: '{plan.question}'.",
        )

        return SQLProviderResponse(
            generated_sql=gen_sql,
            input_tokens=len(plan.question.split()) + 50,
            output_tokens=len(sql.split()),
            model=self._model_name,
            latency_ms=latency,
        )
