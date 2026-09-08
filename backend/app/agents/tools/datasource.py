"""Typed adapter tools wrapping DataSource and Connector services for Agent Runtime."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import (
    DataSourceListInput,
    DataSourcePreviewInput,
    DataSourceQueryInput,
    DataSourceSchemaInput,
)
from app.connectors.application.connector_service import ConnectorService
from app.connectors.application.query_service import QueryService
from app.connectors.application.schema_service import SchemaService
from app.connectors.domain.errors import (
    ConnectorError,
    DataSourceNotFoundError,
    QueryExecutionError,
    QueryTimeoutError,
    ResultSizeExceededError,
)
from app.connectors.domain.models import QueryRequest
from app.rbac.catalog import (
    PERM_DATASOURCE_QUERY,
    PERM_DATASOURCE_READ,
    PERM_DATASOURCE_SCHEMA,
)
from app.sql_agent.exceptions import SQLSecurityViolationError, SQLValidationError


class DataSourceListTool:
    """Tool listing available external data sources for the active tenant."""

    name: str = "datasource.list"
    version: str = "v1.0"
    description: str = (
        "Lists all registered external data sources and connectors available in tenant."
    )
    input_schema: type[BaseModel] = DataSourceListInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASOURCE_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    def __init__(self, connector_service: ConnectorService | None = None) -> None:
        self.connector_service = connector_service or ConnectorService()

    async def validate(self, tool_input: dict[str, Any]) -> DataSourceListInput:
        try:
            return DataSourceListInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, DataSourceListInput)
            else DataSourceListInput.model_validate(validated_input)
        )
        return {
            "action": "list_data_sources",
            "organization_id": str(context.organization_id),
            "limit": inp.limit,
            "offset": inp.offset,
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DataSourceListInput)
            else DataSourceListInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        page = (inp.offset // inp.limit) + 1 if inp.limit > 0 else 1
        try:
            items, total = await self.connector_service.list_data_sources(
                db_session=context.db_session,
                organization_id=context.organization_id,
                page=page,
                page_size=inp.limit,
            )
            duration_ms = (time.perf_counter() - t_start) * 1000
            serialized = [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "type": item.type,
                    "status": item.status,
                }
                for item in items
            ]
            return ToolOutput(
                success=True,
                data={"items": serialized, "total": total},
                evidence_items=[
                    {
                        "evidence_id": "DS_LIST",
                        "source_type": "datasource",
                        "content": f"Found {total} data sources for organization {context.organization_id}",
                        "metadata": {"total": total},
                    }
                ],
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=False,
                error_message=f"Failed to list data sources: {exc}",
                duration_ms=duration_ms,
            )


class DataSourceSchemaTool:
    """Tool discovering unified schema of a target data source."""

    name: str = "datasource.schema"
    version: str = "v1.0"
    description: str = (
        "Retrieves unified relational or tabular schema (tables, columns, types) for a data source."
    )
    input_schema: type[BaseModel] = DataSourceSchemaInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASOURCE_SCHEMA
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    def __init__(
        self,
        schema_service: SchemaService | None = None,
    ) -> None:
        self.schema_service = schema_service or SchemaService()

    async def validate(self, tool_input: dict[str, Any]) -> DataSourceSchemaInput:
        try:
            return DataSourceSchemaInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, DataSourceSchemaInput)
            else DataSourceSchemaInput.model_validate(validated_input)
        )
        return {
            "action": "discover_schema",
            "datasource_id": str(inp.datasource_id),
            "organization_id": str(context.organization_id),
            "refresh": inp.refresh,
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DataSourceSchemaInput)
            else DataSourceSchemaInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        try:
            schema = await self.schema_service.get_schema(
                db_session=context.db_session,
                datasource_id=inp.datasource_id,
                organization_id=context.organization_id,
                user_id=context.user_id,
                force_refresh=inp.refresh,
            )
            duration_ms = (time.perf_counter() - t_start) * 1000
            table_names = [t.name for t in schema.tables]
            return ToolOutput(
                success=True,
                data=schema.model_dump(),
                evidence_items=[
                    {
                        "evidence_id": f"SCHEMA_{inp.datasource_id}",
                        "source_type": "datasource_schema",
                        "content": f"Discovered tables/sheets: {', '.join(table_names[:10])}",
                        "metadata": {
                            "datasource_id": str(inp.datasource_id),
                            "table_count": len(schema.tables),
                        },
                    }
                ],
                duration_ms=duration_ms,
            )
        except DataSourceNotFoundError as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=False,
                error_message=f"Data source not found: {exc}",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=False,
                error_message=f"Schema discovery failed: {exc}",
                duration_ms=duration_ms,
            )


class DataSourcePreviewTool:
    """Tool previewing sample rows from a data source table or sheet."""

    name: str = "datasource.preview"
    version: str = "v1.0"
    description: str = "Retrieves a safe, bounded preview of sample rows from a data source."
    input_schema: type[BaseModel] = DataSourcePreviewInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASOURCE_QUERY
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    def __init__(
        self,
        query_service: QueryService | None = None,
    ) -> None:
        self.query_service = query_service or QueryService()

    async def validate(self, tool_input: dict[str, Any]) -> DataSourcePreviewInput:
        try:
            return DataSourcePreviewInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, DataSourcePreviewInput)
            else DataSourcePreviewInput.model_validate(validated_input)
        )
        return {
            "action": "preview_datasource_rows",
            "datasource_id": str(inp.datasource_id),
            "table_or_sheet": inp.table_or_sheet,
            "limit": min(inp.limit, 100),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DataSourcePreviewInput)
            else DataSourcePreviewInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        bounded_limit = min(max(inp.limit, 1), 50)
        try:
            preview_res = await self.query_service.preview_data(
                db_session=context.db_session,
                datasource_id=inp.datasource_id,
                organization_id=context.organization_id,
                target_name=inp.table_or_sheet,
                max_rows=bounded_limit,
                user_id=context.user_id,
            )
            duration_ms = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=True,
                data=preview_res.model_dump(),
                evidence_items=[
                    {
                        "evidence_id": f"PREVIEW_{inp.datasource_id}",
                        "source_type": "datasource_preview",
                        "content": f"Sample {len(preview_res.rows)} rows from columns {preview_res.columns[:5]}",
                        "metadata": {
                            "datasource_id": str(inp.datasource_id),
                            "sample_size": preview_res.sample_size,
                        },
                    }
                ],
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=False,
                error_message=f"Preview failed: {exc}",
                duration_ms=duration_ms,
            )


class DataSourceQueryTool:
    """Tool executing controlled, policy-checked queries against data sources."""

    name: str = "datasource.query"
    version: str = "v1.0"
    description: str = (
        "Executes AST-validated, read-only SQL or bounded query on an enterprise data source."
    )
    input_schema: type[BaseModel] = DataSourceQueryInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASOURCE_QUERY
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    def __init__(
        self,
        query_service: QueryService | None = None,
    ) -> None:
        self.query_service = query_service or QueryService()

    async def validate(self, tool_input: dict[str, Any]) -> DataSourceQueryInput:
        try:
            return DataSourceQueryInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, DataSourceQueryInput)
            else DataSourceQueryInput.model_validate(validated_input)
        )
        return {
            "action": "execute_datasource_query",
            "datasource_id": str(inp.datasource_id),
            "query": inp.query[:200],
            "timeout_ms": min(inp.timeout_ms, 30000),
            "max_rows": min(inp.max_rows, 1000),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DataSourceQueryInput)
            else DataSourceQueryInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        bounded_timeout = min(max(inp.timeout_ms, 100), 30000)
        bounded_rows = min(max(inp.max_rows, 1), 1000)

        try:
            req = QueryRequest(
                datasource_id=inp.datasource_id,
                organization_id=context.organization_id,
                query=inp.query,
                parameters=inp.parameters,
                timeout_ms=bounded_timeout,
                max_rows=bounded_rows,
            )
            res = await self.query_service.execute_query(
                db_session=context.db_session,
                request=req,
                user_id=context.user_id,
            )
            duration_ms = (time.perf_counter() - t_start) * 1000
            evidence_items = []
            if res.rows:
                evidence_items.append(
                    {
                        "evidence_id": f"QUERY_{inp.datasource_id}",
                        "source_type": "datasource_query",
                        "content": str(res.rows[:3])[:800],
                        "metadata": {
                            "datasource_id": str(inp.datasource_id),
                            "row_count": res.row_count,
                            "execution_time_ms": res.execution_time_ms,
                        },
                    }
                )
            return ToolOutput(
                success=True,
                data=res.model_dump(),
                evidence_items=evidence_items,
                duration_ms=duration_ms,
            )
        except (SQLSecurityViolationError, SQLValidationError) as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=False,
                error_message=f"Query policy violation: {exc}",
                duration_ms=duration_ms,
            )
        except (
            QueryTimeoutError,
            ResultSizeExceededError,
            QueryExecutionError,
            ConnectorError,
        ) as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=False,
                error_message=f"Query failed: {exc}",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=False,
                error_message=f"Unexpected query error: {exc}",
                duration_ms=duration_ms,
            )
