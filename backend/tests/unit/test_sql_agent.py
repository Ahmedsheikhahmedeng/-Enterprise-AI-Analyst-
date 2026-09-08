"""Unit tests for Secure SQL Agent validator, analyzer, provenance, and planning."""

import uuid
from decimal import Decimal

import pytest

from app.sql_agent.analyzer import SQLResultAnalyzer
from app.sql_agent.config import SQLAgentConfig
from app.sql_agent.exceptions import (
    SQLSecurityViolationError,
)
from app.sql_agent.models import (
    ColumnSchema,
    SchemaContext,
    SQLQueryResult,
    TableSchema,
)
from app.sql_agent.planner import SQLPlanner
from app.sql_agent.provenance import SQLProvenanceTracker
from app.sql_agent.providers.deterministic import DeterministicSQLProvider
from app.sql_agent.validator import SQLSecurityValidator


@pytest.fixture
def sample_schema_context() -> SchemaContext:
    """Fixture providing a verified multi-table SchemaContext."""
    return SchemaContext(
        datasource_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        dialect="postgres",
        tables={
            "sales": TableSchema(
                name="sales",
                columns=[
                    ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
                    ColumnSchema(name="quarter", data_type="VARCHAR(10)"),
                    ColumnSchema(name="year", data_type="INTEGER"),
                    ColumnSchema(name="revenue", data_type="NUMERIC(15,2)"),
                ],
            ),
            "customers": TableSchema(
                name="customers",
                columns=[
                    ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
                    ColumnSchema(name="name", data_type="VARCHAR(255)"),
                    ColumnSchema(name="email", data_type="VARCHAR(255)"),
                ],
            ),
            "orders": TableSchema(
                name="orders",
                columns=[
                    ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
                    ColumnSchema(name="customer_id", data_type="INTEGER"),
                    ColumnSchema(name="amount", data_type="NUMERIC(15,2)"),
                ],
            ),
        },
    )


@pytest.fixture
def validator() -> SQLSecurityValidator:
    """Fixture providing a strict SQLSecurityValidator."""
    cfg = SQLAgentConfig(
        enabled=True,
        provider="deterministic",
        model="test-model",
        statement_timeout_ms=3000,
        query_timeout_seconds=5.0,
        max_rows=100,
        max_result_bytes=100000,
        max_joins=2,
        max_ctes=2,
        max_subquery_depth=2,
        schema_cache_ttl_seconds=60,
        prompt_version="sql-v1.0",
        max_llm_cost_per_request=0.10,
    )
    return SQLSecurityValidator(cfg)


class TestSQLSecurityValidator:
    """Test AST security parsing and enforcement rules."""

    def test_valid_select_passes_and_enforces_limit(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        raw_sql = "SELECT quarter, SUM(revenue) FROM sales GROUP BY quarter"
        validated_sql, complexity = validator.validate(raw_sql, sample_schema_context)
        assert "SELECT" in validated_sql
        assert "LIMIT 100" in validated_sql
        assert complexity.table_count == 1
        assert complexity.join_count == 0

    def test_valid_cte_passes(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        raw_sql = (
            "WITH quarterly_sales AS (SELECT quarter, revenue FROM sales) "
            "SELECT quarter, SUM(revenue) FROM quarterly_sales GROUP BY quarter"
        )
        validated_sql, complexity = validator.validate(raw_sql, sample_schema_context)
        assert "quarterly_sales" in validated_sql
        assert complexity.cte_count == 1

    def test_multi_statement_rejected(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        malicious_sql = "SELECT * FROM sales; DROP TABLE customers;"
        with pytest.raises(SQLSecurityViolationError, match="Multiple SQL statements"):
            validator.validate(malicious_sql, sample_schema_context)

    @pytest.mark.parametrize(
        "write_sql",
        [
            "DELETE FROM sales WHERE id = 1;",
            "DROP TABLE sales;",
            "INSERT INTO sales (quarter, revenue) VALUES ('Q1', 100);",
            "UPDATE sales SET revenue = 0;",
            "ALTER TABLE sales ADD COLUMN hack TEXT;",
            "TRUNCATE TABLE sales;",
        ],
    )
    def test_forbidden_write_statements_rejected(
        self,
        validator: SQLSecurityValidator,
        sample_schema_context: SchemaContext,
        write_sql: str,
    ) -> None:
        with pytest.raises(SQLSecurityViolationError):
            validator.validate(write_sql, sample_schema_context)

    def test_unauthorized_table_rejected(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        malicious_sql = "SELECT * FROM users_secrets;"
        with pytest.raises(SQLSecurityViolationError, match="Unauthorized table access"):
            validator.validate(malicious_sql, sample_schema_context)

    def test_unauthorized_column_on_table_rejected(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        malicious_sql = "SELECT sales.password FROM sales;"
        with pytest.raises(SQLSecurityViolationError, match="Unauthorized column 'password'"):
            validator.validate(malicious_sql, sample_schema_context)

    def test_system_catalog_access_rejected(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        malicious_sql = "SELECT * FROM pg_catalog.pg_tables;"
        with pytest.raises(SQLSecurityViolationError, match="Access to system catalog"):
            validator.validate(malicious_sql, sample_schema_context)

    def test_dangerous_system_functions_rejected(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        malicious_sql = "SELECT pg_read_file('etc/passwd') FROM sales;"
        with pytest.raises(SQLSecurityViolationError, match="Forbidden dangerous function"):
            validator.validate(malicious_sql, sample_schema_context)

    def test_excessive_joins_rejected(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        # Validator has max_joins = 2. 3 joins must be rejected
        too_many_joins = (
            "SELECT s.id FROM sales s "
            "JOIN orders o1 ON s.id = o1.id "
            "JOIN orders o2 ON s.id = o2.id "
            "JOIN orders o3 ON s.id = o3.id;"
        )
        with pytest.raises(SQLSecurityViolationError, match="exceeding maximum allowed limit"):
            validator.validate(too_many_joins, sample_schema_context)

    def test_excessive_subquery_depth_rejected(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        # Nesting depth 3 when limit is 2
        deep_sql = (
            "SELECT * FROM ("
            "  SELECT * FROM ("
            "    SELECT * FROM ("
            "      SELECT id FROM sales"
            "    ) s1"
            "  ) s2"
            ") s3;"
        )
        with pytest.raises(SQLSecurityViolationError, match="nesting depth"):
            validator.validate(deep_sql, sample_schema_context)

    def test_limit_clamping(
        self, validator: SQLSecurityValidator, sample_schema_context: SchemaContext
    ) -> None:
        excessive_limit_sql = "SELECT * FROM sales LIMIT 999999;"
        validated_sql, _ = validator.validate(excessive_limit_sql, sample_schema_context)
        assert "LIMIT 100" in validated_sql


class TestSQLResultAnalyzer:
    """Test pandas-based analytical summaries and percent change calculations."""

    def test_aggregations_and_statistics(self) -> None:
        analyzer = SQLResultAnalyzer()
        res = SQLQueryResult(
            columns=["quarter", "revenue"],
            rows=[
                {"quarter": "Q1", "revenue": "100.00"},
                {"quarter": "Q2", "revenue": "150.00"},
                {"quarter": "Q3", "revenue": "120.00"},
            ],
            row_count=3,
        )
        analysis = analyzer.analyze(res, "Quarterly revenue")
        assert analysis.metrics["revenue_sum"] == 370.0
        assert analysis.metrics["revenue_avg"] == 123.33
        assert analysis.metrics["revenue_min"] == 100.0
        assert analysis.metrics["revenue_max"] == 150.0
        assert len(analysis.comparisons) > 0

    def test_percent_change_edge_cases(self) -> None:
        # Zero denominator
        assert SQLResultAnalyzer.calculate_percent_change(0, 100) is None
        # None values
        assert SQLResultAnalyzer.calculate_percent_change(None, 100) is None
        assert SQLResultAnalyzer.calculate_percent_change(100, None) is None
        # Standard growth
        pct = SQLResultAnalyzer.calculate_percent_change(Decimal("100"), Decimal("125"))
        assert pct == 25.0
        # Decline
        pct_decline = SQLResultAnalyzer.calculate_percent_change(200, 150)
        assert pct_decline == -25.0

    def test_empty_results(self) -> None:
        analyzer = SQLResultAnalyzer()
        res = SQLQueryResult(columns=["id"], rows=[], row_count=0)
        analysis = analyzer.analyze(res, "test")
        assert analysis.metrics["row_count"] == 0
        assert "0 rows" in analysis.summary


class TestSQLProvenanceTracker:
    """Test SQL query normalization and deterministic SHA-256 hashing."""

    def test_whitespace_normalization_and_consistent_hash(self) -> None:
        sql1 = "SELECT  id,  revenue \n FROM   sales WHERE year = 2025;"
        sql2 = "SELECT id, revenue FROM sales WHERE year = 2025"

        hash1 = SQLProvenanceTracker.compute_sql_hash(sql1)
        hash2 = SQLProvenanceTracker.compute_sql_hash(sql2)
        assert hash1 == hash2

    def test_different_queries_produce_different_hashes(self) -> None:
        sql1 = "SELECT quarter FROM sales;"
        sql2 = "SELECT year FROM sales;"
        assert SQLProvenanceTracker.compute_sql_hash(sql1) != SQLProvenanceTracker.compute_sql_hash(
            sql2
        )


class TestSQLPlannerAndDeterministicProvider:
    """Test query planning and deterministic SQL code generation."""

    @pytest.mark.asyncio
    async def test_deterministic_provider_matches_revenue_intent(
        self, sample_schema_context: SchemaContext
    ) -> None:
        planner = SQLPlanner()
        plan = planner.plan("What was the total revenue by quarter in 2025?", sample_schema_context)
        assert "sales" in plan.target_tables
        assert "SUM" in plan.suggested_aggregations

        provider = DeterministicSQLProvider()
        resp = await provider.generate_sql(plan, sample_schema_context)
        assert "SELECT quarter, SUM(revenue)" in resp.generated_sql.sql
        assert "sales" in resp.generated_sql.tables_used
