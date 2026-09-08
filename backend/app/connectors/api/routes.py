"""REST API endpoints for Data Connectors & Data Sources."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.api.schemas import (
    DataSourceCreateRequest,
    DataSourceHealthResponse,
    DataSourceListResponse,
    DataSourceQueryRequest,
    DataSourceResponse,
    DataSourceSyncRequest,
    DataSourceSyncResponse,
    DataSourceTestResponse,
    DataSourceUpdateRequest,
)
from app.connectors.application.connection_service import ConnectionService
from app.connectors.application.connector_service import ConnectorService
from app.connectors.application.query_service import QueryService
from app.connectors.application.schema_service import SchemaService
from app.connectors.application.sync_service import SyncService
from app.connectors.domain.errors import (
    DataSourceNotFoundError,
    FileProcessingError,
    FormulaInjectionError,
    InvalidConfigurationError,
    QueryExecutionError,
    QueryTimeoutError,
    ResultSizeExceededError,
    UnsupportedCapabilityError,
)
from app.connectors.domain.models import PreviewResult, QueryRequest, QueryResult, SchemaModel
from app.core.exceptions import BadRequestAppException, NotFoundAppException
from app.db.postgres import get_db_session
from app.rbac.catalog import (
    PERM_DATASOURCE_CREATE,
    PERM_DATASOURCE_DELETE,
    PERM_DATASOURCE_QUERY,
    PERM_DATASOURCE_READ,
    PERM_DATASOURCE_SCHEMA,
    PERM_DATASOURCE_SYNC,
    PERM_DATASOURCE_TEST,
    PERM_DATASOURCE_UPDATE,
)
from app.sql_agent.exceptions import SQLSecurityViolationError, SQLValidationError
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/data-sources", tags=["Data Sources & Connectors"])


def _map_error(exc: Exception) -> Exception:
    if isinstance(exc, DataSourceNotFoundError):
        return NotFoundAppException(message=str(exc), code="DATA_SOURCE_NOT_FOUND")
    if isinstance(exc, (SQLSecurityViolationError, SQLValidationError, FormulaInjectionError)):
        return BadRequestAppException(message=str(exc), code="POLICY_VIOLATION")
    if isinstance(
        exc,
        (
            InvalidConfigurationError,
            UnsupportedCapabilityError,
            FileProcessingError,
            ResultSizeExceededError,
        ),
    ):
        return BadRequestAppException(message=str(exc), code="BAD_REQUEST")
    if isinstance(exc, (QueryExecutionError, QueryTimeoutError)):
        return BadRequestAppException(message=str(exc), code="QUERY_ERROR")
    return exc


def get_connector_service(request: Request) -> ConnectorService:
    redis_client = getattr(request.app.state, "redis_client", None)
    schema_service = SchemaService(redis_client=redis_client)
    return ConnectorService(schema_service=schema_service)


def get_connection_service() -> ConnectionService:
    return ConnectionService()


def get_schema_service(request: Request) -> SchemaService:
    redis_client = getattr(request.app.state, "redis_client", None)
    return SchemaService(redis_client=redis_client)


def get_query_service() -> QueryService:
    return QueryService()


def get_sync_service() -> SyncService:
    return SyncService()


@router.post(
    "",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new DataSource",
)
async def create_data_source(
    payload: DataSourceCreateRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_CREATE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConnectorService, Depends(get_connector_service)],
) -> DataSourceResponse:
    try:
        ds = await service.create_data_source(
            db_session=session,
            organization_id=tenant.organization_id,
            name=payload.name,
            connector_type=payload.type,
            configuration=payload.configuration,
            user_id=tenant.user_id,
        )
        return DataSourceResponse(
            id=ds.id,
            organization_id=ds.organization_id,
            name=ds.name,
            type=ds.type,
            connector_type=ds.type,
            status=ds.status,
            configuration=service.secret_provider.redact_config(ds.configuration),
            description=ds.name,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "",
    response_model=DataSourceListResponse,
    summary="List DataSources for active tenant",
)
async def list_data_sources(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConnectorService, Depends(get_connector_service)],
    limit: int = Query(default=50, ge=1, le=100),
    page: int = Query(default=1, ge=1),
) -> DataSourceListResponse:
    items, total = await service.list_data_sources(
        db_session=session,
        organization_id=tenant.organization_id,
        page=page,
        page_size=limit,
    )
    responses = [
        DataSourceResponse(
            id=ds.id,
            organization_id=ds.organization_id,
            name=ds.name,
            type=ds.type,
            connector_type=ds.type,
            status=ds.status,
            configuration=service.secret_provider.redact_config(ds.configuration),
            description=ds.name,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
        )
        for ds in items
    ]
    return DataSourceListResponse(items=responses, total=total)


@router.get(
    "/{id}",
    response_model=DataSourceResponse,
    summary="Get DataSource details by ID",
)
async def get_data_source(
    id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConnectorService, Depends(get_connector_service)],
) -> DataSourceResponse:
    try:
        ds = await service.get_data_source(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
        )
        return DataSourceResponse(
            id=ds.id,
            organization_id=ds.organization_id,
            name=ds.name,
            type=ds.type,
            connector_type=ds.type,
            status=ds.status,
            configuration=service.secret_provider.redact_config(ds.configuration),
            description=ds.name,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.patch(
    "/{id}",
    response_model=DataSourceResponse,
    summary="Update DataSource configuration or metadata",
)
async def update_data_source(
    id: uuid.UUID,
    payload: DataSourceUpdateRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_UPDATE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConnectorService, Depends(get_connector_service)],
) -> DataSourceResponse:
    try:
        ds = await service.update_data_source(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
            name=payload.name,
            configuration=payload.configuration,
            user_id=tenant.user_id,
        )
        return DataSourceResponse(
            id=ds.id,
            organization_id=ds.organization_id,
            name=ds.name,
            type=ds.type,
            connector_type=ds.type,
            status=ds.status,
            configuration=service.secret_provider.redact_config(ds.configuration),
            description=ds.name,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a DataSource",
)
async def delete_data_source(
    id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_DELETE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConnectorService, Depends(get_connector_service)],
) -> None:
    try:
        await service.delete_data_source(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/{id}/test",
    response_model=DataSourceTestResponse,
    summary="Test live connectivity to DataSource",
)
async def test_data_source_connection(
    id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_TEST))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    connection_service: Annotated[ConnectionService, Depends(get_connection_service)],
) -> DataSourceTestResponse:
    try:
        res = await connection_service.test_connection(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
        )
        return DataSourceTestResponse(
            success=res.success,
            latency_ms=res.latency_ms,
            message=res.message,
            tested_at=res.tested_at,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/{id}/schema",
    response_model=SchemaModel,
    summary="Discover unified schema of DataSource",
)
async def get_data_source_schema(
    id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_SCHEMA))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    schema_service: Annotated[SchemaService, Depends(get_schema_service)],
    refresh: bool = Query(default=False, description="Force refresh cache"),
) -> SchemaModel:
    try:
        return await schema_service.get_schema(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            force_refresh=refresh,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/{id}/preview",
    response_model=PreviewResult,
    summary="Preview sample data rows from DataSource",
)
async def preview_data_source(
    id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_QUERY))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    query_service: Annotated[QueryService, Depends(get_query_service)],
    table_or_sheet: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> PreviewResult:
    try:
        return await query_service.preview_data(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
            target_name=table_or_sheet,
            max_rows=limit,
            user_id=tenant.user_id,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/{id}/query",
    response_model=QueryResult,
    summary="Execute validated query against DataSource",
)
async def execute_data_source_query(
    id: uuid.UUID,
    payload: DataSourceQueryRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_QUERY))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    query_service: Annotated[QueryService, Depends(get_query_service)],
) -> QueryResult:
    try:
        req = QueryRequest(
            datasource_id=id,
            organization_id=tenant.organization_id,
            query=payload.query,
            parameters=payload.parameters,
            timeout_ms=payload.timeout_ms,
            max_rows=payload.max_rows,
        )
        return await query_service.execute_query(
            db_session=session,
            request=req,
            user_id=tenant.user_id,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/{id}/sync",
    response_model=DataSourceSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger full synchronization for DataSource",
)
async def sync_data_source(
    id: uuid.UUID,
    payload: DataSourceSyncRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_SYNC))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    sync_service: Annotated[SyncService, Depends(get_sync_service)],
) -> DataSourceSyncResponse:
    try:
        run_model = await sync_service.execute_sync(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
            sync_type=payload.sync_type.value,
            user_id=tenant.user_id,
        )
        return DataSourceSyncResponse(
            sync_id=run_model.id,
            datasource_id=id,
            status=run_model.status,
            sync_type=run_model.sync_type,
            started_at=run_model.started_at,
            message="Synchronization completed successfully"
            if run_model.status.value == "COMPLETED"
            else f"Synchronization ended with status {run_model.status.value}",
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/{id}/health",
    response_model=DataSourceHealthResponse,
    summary="Health check for DataSource",
)
async def get_data_source_health(
    id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DATASOURCE_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
    connection_service: Annotated[ConnectionService, Depends(get_connection_service)],
) -> DataSourceHealthResponse:
    try:
        ds = await connector_service.get_data_source(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
        )
        res = await connection_service.test_connection(
            db_session=session,
            datasource_id=id,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
        )
        return DataSourceHealthResponse(
            datasource_id=ds.id,
            connector_type=ds.type,
            status=ds.status,
            healthy=res.success,
            last_checked_at=res.tested_at,
            metrics={
                "latency_ms": res.latency_ms,
                "success": res.success,
            },
        )
    except Exception as exc:
        raise _map_error(exc) from exc
