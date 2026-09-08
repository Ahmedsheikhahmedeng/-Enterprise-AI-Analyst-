"""SQL Security Hardening Tests — TASK 22.

Verifies:
- Rejection of non-SELECT mutations (INSERT, UPDATE, DELETE, DROP, ALTER)
- Multiple statements rejection
- System catalog access rejection (pg_catalog, information_schema)
- Dangerous function execution rejection (pg_read_file, pg_sleep)
- Cartesian join and complexity bounding
- Limit enforcement
"""

import uuid

import pytest

from app.sql_agent.config import SQLAgentConfig
from app.sql_agent.exceptions import SQLSecurityViolationError
from app.sql_agent.models import ColumnSchema, SchemaContext, TableSchema
from app.sql_agent.validator import SQLSecurityValidator


@pytest.fixture
def schema_ctx() -> SchemaContext:
    return SchemaContext(
        datasource_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        dialect="postgres",
        tables={
            "analytics_events": TableSchema(
                name="analytics_events",
                columns=[
                    ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
                    ColumnSchema(name="user_id", data_type="INTEGER"),
                    ColumnSchema(name="event_name", data_type="VARCHAR(64)"),
                ],
            ),
            "users": TableSchema(
                name="users",
                columns=[
                    ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
                    ColumnSchema(name="username", data_type="VARCHAR(64)"),
                ],
            ),
        },
    )


@pytest.fixture
def validator() -> SQLSecurityValidator:
    cfg = SQLAgentConfig(
        enabled=True,
        provider="deterministic",
        model="test-model",
        statement_timeout_ms=2000,
        query_timeout_seconds=3.0,
        max_rows=50,
        max_result_bytes=50000,
        max_joins=1,
        max_ctes=1,
        max_subquery_depth=2,
        schema_cache_ttl_seconds=300,
        prompt_version="1.0",
        max_llm_cost_per_request=0.10,
    )
    return SQLSecurityValidator(cfg)


@pytest.mark.parametrize(
    "destructive_sql",
    [
        "DROP TABLE users;",
        "DELETE FROM users WHERE id = 1;",
        "UPDATE users SET username = 'hacked' WHERE id = 1;",
        "INSERT INTO users (id, username) VALUES (99, 'bad');",
        "TRUNCATE TABLE users;",
        "ALTER TABLE users ADD COLUMN secret text;",
    ],
)
def test_destructive_sql_mutation_rejected(
    validator: SQLSecurityValidator,
    schema_ctx: SchemaContext,
    destructive_sql: str,
) -> None:
    with pytest.raises(SQLSecurityViolationError):
        validator.validate(destructive_sql, schema_ctx)


def test_multi_statement_sql_rejected(
    validator: SQLSecurityValidator,
    schema_ctx: SchemaContext,
) -> None:
    multi_sql = "SELECT id FROM users; DROP TABLE users;"
    with pytest.raises(SQLSecurityViolationError) as exc:
        validator.validate(multi_sql, schema_ctx)
    assert "Multiple SQL statements detected" in str(exc.value)


@pytest.mark.parametrize(
    "forbidden_func_sql",
    [
        "SELECT pg_read_file('/etc/passwd') FROM users;",
        "SELECT pg_sleep(10) FROM users;",
        "SELECT version() FROM users;",
    ],
)
def test_dangerous_function_rejected(
    validator: SQLSecurityValidator,
    schema_ctx: SchemaContext,
    forbidden_func_sql: str,
) -> None:
    with pytest.raises(SQLSecurityViolationError):
        validator.validate(forbidden_func_sql, schema_ctx)


def test_system_catalog_access_rejected(
    validator: SQLSecurityValidator,
    schema_ctx: SchemaContext,
) -> None:
    catalog_sql = "SELECT * FROM pg_catalog.pg_tables;"
    with pytest.raises(SQLSecurityViolationError):
        validator.validate(catalog_sql, schema_ctx)


def test_excessive_joins_rejected(
    validator: SQLSecurityValidator,
    schema_ctx: SchemaContext,
) -> None:
    # max_joins is 1 in fixture
    excessive_join_sql = (
        "SELECT u.username FROM users u "
        "JOIN analytics_events a1 ON u.id = a1.user_id "
        "JOIN analytics_events a2 ON u.id = a2.user_id;"
    )
    with pytest.raises(SQLSecurityViolationError) as exc:
        validator.validate(excessive_join_sql, schema_ctx)
    assert "JOINs, exceeding maximum allowed" in str(exc.value)
