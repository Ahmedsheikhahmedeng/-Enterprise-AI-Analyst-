"""Unified query execution and data preview service enforcing AST safety and limits."""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.domain.enums import ConnectorType
from app.connectors.domain.errors import (
    DataSourceNotFoundError,
)
from app.connectors.domain.models import PreviewResult, QueryRequest, QueryResult
from app.connectors.infrastructure.registry import ConnectorRegistry, get_connector_registry
from app.connectors.infrastructure.secrets import SecretProvider, get_secret_provider
from app.core.logging import get_logger
from app.models.audit import AuditLog
from app.models.data_source import DataSource
from app.sql_agent.models import SchemaContext
from app.sql_agent.validator import SQLSecurityValidator

logger = get_logger("connectors.query_service")

MAX_PREVIEW_ROWS_LIMIT = 100


class QueryService:
    """Coordinates query validation, execution bounding, and provenance generation."""

    def __init__(
        self,
        registry: ConnectorRegistry | None = None,
        secret_provider: SecretProvider | None = None,
        sql_validator: SQLSecurityValidator | None = None,
    ) -> None:
        self.registry = registry or get_connector_registry()
        self.secret_provider = secret_provider or get_secret_provider()
        self.sql_validator = sql_validator or SQLSecurityValidator()

    async def execute_query(
        self,
        db_session: AsyncSession,
        request: QueryRequest,
        user_id: uuid.UUID | None = None,
    ) -> QueryResult:
        """Validate query safety, execute via connector, generate provenance, and audit."""
        # 1. Tenant-isolated DataSource lookup
        stmt = select(DataSource).where(
            DataSource.id == request.datasource_id,
            DataSource.organization_id == request.organization_id,
        )
        res = await db_session.execute(stmt)
        ds = res.scalars().first()
        if not ds:
            raise DataSourceNotFoundError(request.datasource_id)

        connector = self.registry.get(ds.type)
        connector.capabilities.require_query()

        # 2. Mandatory SQL validation for relational sources
        if ds.type == ConnectorType.POSTGRESQL.value:
            import sqlglot
            from sqlglot import exp

            from app.sql_agent.models import TableSchema as SqlTableSchema

            tables_dict: dict[str, SqlTableSchema] = {}
            try:
                parsed = sqlglot.parse_one(request.query, read="postgres")
                for tbl in parsed.find_all(exp.Table):
                    t_name = tbl.name.lower()
                    if t_name:
                        tables_dict[t_name] = SqlTableSchema(name=t_name, columns=[])
            except Exception:
                pass

            schema_context = SchemaContext(
                datasource_id=request.datasource_id,
                organization_id=request.organization_id,
                dialect="postgres",
                tables=tables_dict,
            )
            self.sql_validator.validate(request.query, schema_context)

        # 3. Decrypt configuration for runtime execution
        runtime_config = self.secret_provider.decrypt_config(ds.configuration)

        # 4. Execute via connector
        query_result = await connector.execute_query(request, runtime_config)

        # 5. Audit log without sensitive payload
        q_hash = hashlib.sha256(request.query.encode("utf-8")).hexdigest()
        audit_entry = AuditLog(
            organization_id=request.organization_id,
            user_id=user_id,
            action="QUERY_EXECUTED",
            resource_type="data_source",
            resource_id=str(request.datasource_id),
            metadata_={
                "query_hash": q_hash,
                "row_count": query_result.row_count,
                "execution_time_ms": query_result.execution_time_ms,
                "connector_type": ds.type,
            },
        )
        db_session.add(audit_entry)
        await db_session.commit()

        from app.observability.instrumentation.connectors import get_connector_instrumentation

        get_connector_instrumentation().record_query_execution(
            connector_type=ds.type,
            success=True,
            duration_ms=query_result.execution_time_ms,
            row_count=query_result.row_count,
        )

        return query_result

    async def preview_data(
        self,
        db_session: AsyncSession,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        target_name: str | None = None,
        max_rows: int = 50,
        user_id: uuid.UUID | None = None,
    ) -> PreviewResult:
        """Fetch safe, bounded sample preview of a table, view, or sheet."""
        bounded_rows = min(max(1, max_rows), MAX_PREVIEW_ROWS_LIMIT)

        stmt = select(DataSource).where(
            DataSource.id == datasource_id,
            DataSource.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        ds = res.scalars().first()
        if not ds:
            raise DataSourceNotFoundError(datasource_id)

        connector = self.registry.get(ds.type)
        runtime_config = self.secret_provider.decrypt_config(ds.configuration)

        preview_res = await connector.preview_data(
            datasource_id=datasource_id,
            organization_id=organization_id,
            config=runtime_config,
            target_name=target_name,
            max_rows=bounded_rows,
        )

        # Audit preview
        audit_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="DATA_PREVIEWED",
            resource_type="data_source",
            resource_id=str(datasource_id),
            metadata_={
                "target_name": preview_res.target_name,
                "row_count": len(preview_res.rows),
                "connector_type": ds.type,
            },
        )
        db_session.add(audit_entry)
        await db_session.commit()

        return preview_res
