"""Central ConnectorService coordinating DataSource CRUD, encryption, and cache invalidation."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.application.schema_service import SchemaService
from app.connectors.domain.enums import ConnectionStatus, ConnectorType
from app.connectors.domain.errors import DataSourceNotFoundError, InvalidConfigurationError
from app.connectors.infrastructure.registry import ConnectorRegistry, get_connector_registry
from app.connectors.infrastructure.secrets import SecretProvider, get_secret_provider
from app.core.logging import get_logger
from app.models.audit import AuditLog
from app.models.data_source import DataSource

logger = get_logger("connectors.connector_service")


class ConnectorService:
    """Enterprise DataSource coordinator ensuring tenant isolation, secret safety, and lifecycle management."""

    def __init__(
        self,
        registry: ConnectorRegistry | None = None,
        secret_provider: SecretProvider | None = None,
        schema_service: SchemaService | None = None,
    ) -> None:
        self.registry = registry or get_connector_registry()
        self.secret_provider = secret_provider or get_secret_provider()
        self.schema_service = schema_service or SchemaService(
            registry=self.registry, secret_provider=self.secret_provider
        )

    async def create_data_source(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        name: str,
        connector_type: str | ConnectorType,
        configuration: dict[str, Any],
        user_id: uuid.UUID | None = None,
    ) -> DataSource:
        """Register a new data source, encrypting credentials at rest."""
        type_str = str(
            connector_type.value if hasattr(connector_type, "value") else connector_type
        ).lower()
        if not self.registry.has(type_str):
            raise InvalidConfigurationError(type_str, f"Unsupported connector type '{type_str}'.")

        # Encrypt sensitive configuration parameters at rest
        encrypted_config = self.secret_provider.encrypt_config(configuration)

        ds = DataSource(
            organization_id=organization_id,
            name=name,
            type=type_str,
            status=ConnectionStatus.REGISTERED.value,
            configuration=encrypted_config,
            created_by=user_id,
        )
        db_session.add(ds)
        await db_session.flush()

        # Audit log (redacted)
        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="DATASOURCE_CREATED",
                resource_type="data_source",
                resource_id=str(ds.id),
                metadata_={
                    "name": name,
                    "connector_type": type_str,
                },
            )
        )
        await db_session.commit()
        await db_session.refresh(ds)
        return ds

    async def get_data_source(
        self,
        db_session: AsyncSession,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> DataSource:
        """Retrieve data source within tenant boundary; raises DataSourceNotFoundError if absent."""
        stmt = select(DataSource).where(
            DataSource.id == datasource_id,
            DataSource.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        ds = res.scalars().first()
        if not ds:
            raise DataSourceNotFoundError(datasource_id)
        return ds

    async def list_data_sources(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[DataSource], int]:
        """Fetch paginated data sources strictly bounded to caller's tenant."""
        safe_page = max(1, page)
        safe_size = min(max(1, page_size), 100)
        offset = (safe_page - 1) * safe_size

        count_stmt = select(func.count(DataSource.id)).where(
            DataSource.organization_id == organization_id
        )
        total = (await db_session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(DataSource)
            .where(DataSource.organization_id == organization_id)
            .order_by(DataSource.created_at.desc())
            .offset(offset)
            .limit(safe_size)
        )
        res = await db_session.execute(stmt)
        items = list(res.scalars().all())
        return items, total

    async def update_data_source(
        self,
        db_session: AsyncSession,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        name: str | None = None,
        configuration: dict[str, Any] | None = None,
        status: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> DataSource:
        """Update data source metadata or configuration, re-encrypting secrets and clearing cache."""
        ds = await self.get_data_source(db_session, datasource_id, organization_id)

        config_changed = False
        if name is not None:
            ds.name = name
        if status is not None:
            ds.status = status
        if configuration is not None:
            # Merge and encrypt
            merged = dict(ds.configuration)
            merged.update(configuration)
            ds.configuration = self.secret_provider.encrypt_config(merged)
            config_changed = True

        ds.updated_at = datetime.now(UTC)

        # Invalidate schema cache if configuration changed
        if config_changed:
            await self.schema_service.invalidate_schema_cache(organization_id, datasource_id)

        action = (
            "DATASOURCE_DISABLED"
            if status == ConnectionStatus.DISABLED.value
            else "DATASOURCE_UPDATED"
        )
        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action=action,
                resource_type="data_source",
                resource_id=str(datasource_id),
                metadata_={"status": ds.status, "name": ds.name},
            )
        )
        await db_session.commit()
        await db_session.refresh(ds)
        return ds

    async def delete_data_source(
        self,
        db_session: AsyncSession,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Remove data source, clear cached schemas, and emit audit event."""
        ds = await self.get_data_source(db_session, datasource_id, organization_id)

        await self.schema_service.invalidate_schema_cache(organization_id, datasource_id)
        await db_session.delete(ds)

        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="DATASOURCE_DELETED",
                resource_type="data_source",
                resource_id=str(datasource_id),
                metadata_={"name": ds.name, "connector_type": ds.type},
            )
        )
        await db_session.commit()
