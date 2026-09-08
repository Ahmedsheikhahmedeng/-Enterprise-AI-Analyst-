"""Schema discovery and Redis-based schema caching service."""

import json
import uuid

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.domain.errors import DataSourceNotFoundError
from app.connectors.domain.models import SchemaModel
from app.connectors.infrastructure.registry import ConnectorRegistry, get_connector_registry
from app.connectors.infrastructure.secrets import SecretProvider, get_secret_provider
from app.core.logging import get_logger
from app.models.audit import AuditLog
from app.models.data_source import DataSource

logger = get_logger("connectors.schema_service")

DEFAULT_SCHEMA_TTL_SECONDS = 3600  # 1 hour


class SchemaService:
    """Discovers normalized schemas and provides tenant-scoped Redis caching."""

    def __init__(
        self,
        redis_client: Redis | None = None,
        registry: ConnectorRegistry | None = None,
        secret_provider: SecretProvider | None = None,
        default_ttl_seconds: int = DEFAULT_SCHEMA_TTL_SECONDS,
    ) -> None:
        self.redis = redis_client
        self.registry = registry or get_connector_registry()
        self.secret_provider = secret_provider or get_secret_provider()
        self.ttl = default_ttl_seconds
        # In-memory fallback cache if Redis is not provided
        self._local_cache: dict[str, str] = {}

    def _cache_key(
        self, organization_id: uuid.UUID, datasource_id: uuid.UUID, version: int = 1
    ) -> str:
        """Construct isolated tenant & datasource cache key."""
        return f"schema:{organization_id}:{datasource_id}:{version}"

    async def get_cached_schema(
        self,
        organization_id: uuid.UUID,
        datasource_id: uuid.UUID,
        version: int = 1,
    ) -> SchemaModel | None:
        """Fetch schema from Redis or local cache if present."""
        key = self._cache_key(organization_id, datasource_id, version)
        try:
            raw = None
            if self.redis:
                raw = await self.redis.get(key)
            else:
                raw = self._local_cache.get(key)

            if raw:
                data = json.loads(raw)
                return SchemaModel.model_validate(data)
        except Exception as exc:
            logger.warning("Error reading schema from cache: %s", exc)
        return None

    async def cache_schema(
        self,
        schema: SchemaModel,
        version: int = 1,
    ) -> None:
        """Persist discovered schema into Redis cache."""
        key = self._cache_key(schema.organization_id, schema.datasource_id, version)
        payload = schema.model_dump_json()
        try:
            if self.redis:
                await self.redis.set(key, payload, ex=self.ttl)
            else:
                self._local_cache[key] = payload
        except Exception as exc:
            logger.warning("Error writing schema to cache: %s", exc)

    async def invalidate_schema_cache(
        self,
        organization_id: uuid.UUID,
        datasource_id: uuid.UUID,
    ) -> None:
        """Purge cached schema entries across versions."""
        pattern = f"schema:{organization_id}:{datasource_id}:*"
        try:
            if self.redis:
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
            else:
                to_del = [
                    k
                    for k in self._local_cache
                    if k.startswith(f"schema:{organization_id}:{datasource_id}:")
                ]
                for k in to_del:
                    self._local_cache.pop(k, None)
        except Exception as exc:
            logger.warning("Error invalidating schema cache: %s", exc)

    async def get_schema(
        self,
        db_session: AsyncSession,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        force_refresh: bool = False,
    ) -> SchemaModel:
        """Fetch schema, utilizing Redis cache unless force_refresh is requested."""
        if not force_refresh:
            cached = await self.get_cached_schema(organization_id, datasource_id)
            if cached:
                return cached

        # Fetch DataSource record
        stmt = select(DataSource).where(
            DataSource.id == datasource_id,
            DataSource.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        ds = res.scalars().first()
        if not ds:
            raise DataSourceNotFoundError(datasource_id)

        connector = self.registry.get(ds.type)
        connector.capabilities.require_schema()

        # Decrypt config for schema discovery
        runtime_config = self.secret_provider.decrypt_config(ds.configuration)

        import time

        t0 = time.perf_counter()
        schema = await connector.get_schema(
            datasource_id=datasource_id,
            organization_id=organization_id,
            config=runtime_config,
        )
        duration_ms = (time.perf_counter() - t0) * 1000

        # Cache schema
        await self.cache_schema(schema)

        # Audit log
        audit_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="SCHEMA_DISCOVERED",
            resource_type="data_source",
            resource_id=str(datasource_id),
            metadata_={
                "table_count": len(schema.tables),
                "connector_type": ds.type,
                "force_refresh": force_refresh,
                "duration_ms": duration_ms,
            },
        )
        db_session.add(audit_entry)
        await db_session.commit()

        from app.observability.instrumentation.connectors import get_connector_instrumentation

        get_connector_instrumentation().record_schema_discovery(ds.type, True, duration_ms)

        return schema
