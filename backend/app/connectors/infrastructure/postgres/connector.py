"""PostgreSQL connector implementing schema discovery and AST-guarded read-only query execution."""

import asyncio
import contextlib
import time
import uuid
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from app.connectors.domain.capabilities import ConnectorCapabilities
from app.connectors.domain.enums import ConnectorType
from app.connectors.domain.errors import (
    QueryExecutionError,
    QueryTimeoutError,
    ResultSizeExceededError,
    SchemaDiscoveryError,
)
from app.connectors.domain.models import (
    ColumnSchema,
    ConnectionTestResult,
    PreviewResult,
    QueryRequest,
    QueryResult,
    SchemaModel,
    TableSchema,
)
from app.connectors.domain.protocols import DataConnector
from app.core.logging import get_logger
from app.sql_agent.models import SchemaContext
from app.sql_agent.validator import SQLSecurityValidator

logger = get_logger("connectors.postgres")


class PostgreSQLConnector(DataConnector):
    """Production PostgreSQL data connector."""

    def __init__(self, validator: SQLSecurityValidator | None = None) -> None:
        self._capabilities = ConnectorCapabilities(
            schema_read=True,
            query=True,
            write=False,
            sync=True,
            streaming=True,
            cdc=False,
            files=False,
            embedding=False,
        )
        self.validator = validator or SQLSecurityValidator()

    @property
    def capabilities(self) -> ConnectorCapabilities:
        return self._capabilities

    def _build_conn_params(self, config: dict[str, Any]) -> dict[str, Any]:
        """Normalize configuration into asyncpg connection arguments."""
        # Support dsn or individual parameters
        params: dict[str, Any] = {}
        if "dsn" in config and config["dsn"]:
            params["dsn"] = str(config["dsn"])
        else:
            params["host"] = str(config.get("host", "localhost"))
            params["port"] = int(config.get("port", 5432))
            params["database"] = str(config.get("database", "postgres"))
            params["user"] = str(config.get("user", "postgres"))
            if "password" in config and config["password"]:
                params["password"] = str(config["password"])

        if "ssl" in config:
            params["ssl"] = config["ssl"]
        return params

    async def test_connection(
        self,
        config: dict[str, Any],
        timeout_seconds: float = 5.0,
    ) -> ConnectionTestResult:
        """Test live connectivity to PostgreSQL database."""
        conn_params = self._build_conn_params(config)
        t0 = time.perf_counter()
        conn = None
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(**conn_params),
                timeout=timeout_seconds,
            )
            version_str = await conn.fetchval("SHOW server_version;")
            latency_ms = (time.perf_counter() - t0) * 1000
            return ConnectionTestResult(
                success=True,
                latency_ms=latency_ms,
                message="Connected successfully to PostgreSQL database.",
                server_version=str(version_str),
            )
        except TimeoutError:
            latency_ms = (time.perf_counter() - t0) * 1000
            return ConnectionTestResult(
                success=False,
                latency_ms=latency_ms,
                message=f"Connection timed out after {timeout_seconds}s.",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            # Redact raw credentials from error message
            err_msg = str(exc)
            if "password" in err_msg.lower():
                err_msg = "Authentication failed (invalid credentials)."
            return ConnectionTestResult(
                success=False,
                latency_ms=latency_ms,
                message=f"Connection failed: {err_msg}",
            )
        finally:
            if conn:
                with contextlib.suppress(Exception):
                    await conn.close()

    async def get_schema(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
    ) -> SchemaModel:
        """Discover database schemas, tables, columns, primary keys, foreign keys, and indexes."""
        conn_params = self._build_conn_params(config)
        conn = None
        try:
            conn = await asyncio.wait_for(asyncpg.connect(**conn_params), timeout=15.0)

            # 1. Discover user tables
            tables_query = """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY table_schema, table_name;
            """
            await conn.fetch(tables_query)

            # 2. Discover columns
            columns_query = """
                SELECT table_schema, table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY table_schema, table_name, ordinal_position;
            """
            col_rows = await conn.fetch(columns_query)

            # 3. Discover primary keys
            pk_query = """
                SELECT tc.table_schema, tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast');
            """
            pk_rows = await conn.fetch(pk_query)

            # 4. Discover foreign keys
            fk_query = """
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast');
            """
            fk_rows = await conn.fetch(fk_query)

            # Group columns, PKs, FKs by table
            tables_map: dict[tuple[str, str], list[ColumnSchema]] = {}
            pk_map: dict[tuple[str, str], set[str]] = {}
            fk_map: dict[tuple[str, str, str], str] = {}

            for r in pk_rows:
                key = (str(r["table_schema"]), str(r["table_name"]))
                pk_map.setdefault(key, set()).add(str(r["column_name"]))

            for r in fk_rows:
                fk_key = (str(r["table_schema"]), str(r["table_name"]), str(r["column_name"]))
                fk_map[fk_key] = f"{r['foreign_table_name']}.{r['foreign_column_name']}"

            for r in col_rows:
                t_key = (str(r["table_schema"]), str(r["table_name"]))
                col_name = str(r["column_name"])
                is_pk = col_name in pk_map.get(t_key, set())
                fk_target = fk_map.get((t_key[0], t_key[1], col_name))
                col_schema = ColumnSchema(
                    name=col_name,
                    data_type=str(r["data_type"]),
                    nullable=(str(r["is_nullable"]).upper() == "YES"),
                    primary_key=is_pk,
                    foreign_key=fk_target,
                )
                tables_map.setdefault(t_key, []).append(col_schema)

            table_schemas: list[TableSchema] = []
            for (t_schema, t_name), columns in tables_map.items():
                pks = list(pk_map.get((t_schema, t_name), set()))
                table_schemas.append(
                    TableSchema(
                        name=t_name,
                        schema_name=t_schema,
                        columns=columns,
                        primary_keys=pks,
                    )
                )

            return SchemaModel(
                datasource_id=datasource_id,
                organization_id=organization_id,
                connector_type=ConnectorType.POSTGRESQL,
                tables=table_schemas,
            )
        except Exception as exc:
            logger.error("Failed discovering PostgreSQL schema for %s: %s", datasource_id, exc)
            raise SchemaDiscoveryError(datasource_id, str(exc)) from exc
        finally:
            if conn:
                with contextlib.suppress(Exception):
                    await conn.close()

    async def execute_query(
        self,
        request: QueryRequest,
        config: dict[str, Any],
    ) -> QueryResult:
        """Execute read-only SQL query subject to AST security validation and resource bounds."""
        # 1. Validate SQL via AST validator
        raw_sql = request.query.strip()
        schema_context = SchemaContext(
            datasource_id=request.datasource_id,
            organization_id=request.organization_id,
            dialect="postgres",
            tables={},
        )
        self.validator.validate(raw_sql, schema_context)

        conn_params = self._build_conn_params(config)
        conn = None
        t0 = time.perf_counter()
        timeout_s = request.timeout_ms / 1000.0

        try:
            conn = await asyncio.wait_for(asyncpg.connect(**conn_params), timeout=10.0)

            # Enforce read-only transaction and statement timeout
            await conn.execute("BEGIN TRANSACTION READ ONLY;")
            await conn.execute(f"SET LOCAL statement_timeout = {int(request.timeout_ms)};")

            # Execute query
            params_list = list(request.parameters.values()) if request.parameters else []
            rows_data = await asyncio.wait_for(
                conn.fetch(raw_sql, *params_list),
                timeout=timeout_s,
            )

            await conn.execute("COMMIT;")

            if len(rows_data) > request.max_rows:
                raise ResultSizeExceededError(request.datasource_id, request.max_rows)

            columns: list[str] = list(rows_data[0].keys()) if rows_data else []
            formatted_rows: list[dict[str, Any]] = [dict(r) for r in rows_data]
            exec_time_ms = (time.perf_counter() - t0) * 1000

            import hashlib

            query_hash = hashlib.sha256(raw_sql.encode("utf-8")).hexdigest()

            return QueryResult(
                columns=columns,
                rows=formatted_rows,
                row_count=len(formatted_rows),
                execution_time_ms=exec_time_ms,
                datasource_id=request.datasource_id,
                provenance={
                    "organization_id": str(request.organization_id),
                    "datasource_id": str(request.datasource_id),
                    "connector_type": ConnectorType.POSTGRESQL.value,
                    "query_hash": query_hash,
                    "row_count": len(formatted_rows),
                    "execution_time_ms": exec_time_ms,
                },
            )
        except TimeoutError as exc:
            raise QueryTimeoutError(request.datasource_id, request.timeout_ms) from exc
        except ResultSizeExceededError:
            raise
        except Exception as exc:
            err_msg = str(exc)
            if "canceling statement due to statement timeout" in err_msg.lower():
                raise QueryTimeoutError(request.datasource_id, request.timeout_ms) from exc
            logger.error("PostgreSQL query execution failed: %s", err_msg)
            raise QueryExecutionError(request.datasource_id, err_msg, raw_sql[:100]) from exc
        finally:
            if conn:
                with contextlib.suppress(Exception):
                    await conn.close()

    async def preview_data(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
        target_name: str | None = None,
        max_rows: int = 50,
    ) -> PreviewResult:
        """Fetch safe bounded preview rows for a table."""
        bounded_rows = min(max_rows, 100)
        target = target_name or "public.customers"

        # Sanitize identifier to alphanumeric + underscore + period
        import re

        clean_target = re.sub(r"[^\w\.]", "", target)

        query = f"SELECT * FROM {clean_target} LIMIT {bounded_rows};"
        query_req = QueryRequest(
            datasource_id=datasource_id,
            organization_id=organization_id,
            query=query,
            timeout_ms=5000,
            max_rows=bounded_rows,
        )
        res = await self.execute_query(query_req, config)

        col_schemas = [
            ColumnSchema(name=c, data_type="unknown", nullable=True) for c in res.columns
        ]
        return PreviewResult(
            datasource_id=datasource_id,
            target_name=clean_target,
            columns=col_schemas,
            rows=res.rows,
            total_rows_estimate=res.row_count,
        )

    async def health_check(self, config: dict[str, Any]) -> bool:
        """Fast liveness ping."""
        res = await self.test_connection(config, timeout_seconds=3.0)
        return res.success
