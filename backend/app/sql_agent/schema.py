"""Schema discovery and catalog introspection service for SQL Agent."""

import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.data_source import DataSource
from app.models.dataset import Dataset
from app.sql_agent.config import SQLAgentConfig, get_sql_agent_config
from app.sql_agent.exceptions import (
    SQLDataSourceNotFoundError,
    SQLTenantMismatchError,
)
from app.sql_agent.models import (
    ColumnSchema,
    RelationshipSchema,
    SchemaContext,
    TableSchema,
)

logger = get_logger("sql_agent.schema")


class SchemaDiscoveryService:
    """Discovers, validates, and caches tenant-scoped relational schemas."""

    def __init__(self, config: SQLAgentConfig | None = None) -> None:
        self.config = config or get_sql_agent_config()
        # In-memory tenant-scoped schema cache:
        # (org_id, datasource_id) -> (timestamp, SchemaContext)
        self._cache: dict[tuple[UUID, UUID], tuple[float, SchemaContext]] = {}

    def invalidate(self, organization_id: UUID, datasource_id: UUID) -> None:
        """Explicitly purge schema entry from in-memory cache."""
        self._cache.pop((organization_id, datasource_id), None)

    async def get_schema_context(
        self,
        datasource_id: UUID,
        organization_id: UUID,
        session: AsyncSession,
    ) -> SchemaContext:
        """Resolve schema context for a data source or dataset strictly scoped to tenant."""
        now = time.time()
        cache_key = (organization_id, datasource_id)

        # 1. Check in-memory cache
        if cache_key in self._cache:
            cached_time, cached_schema = self._cache[cache_key]
            if now - cached_time < self.config.schema_cache_ttl_seconds:
                return cached_schema

        # 2. Check if datasource_id matches a DataSource
        ds_stmt = select(DataSource).where(DataSource.id == datasource_id)
        ds_res = await session.execute(ds_stmt)
        data_source = ds_res.scalar_one_or_none()

        if data_source is not None:
            if data_source.organization_id != organization_id:
                logger.warning(
                    "Cross-tenant DataSource access attempt detected",
                    datasource_id=str(datasource_id),
                    requested_org=str(organization_id),
                    actual_org=str(data_source.organization_id),
                )
                raise SQLTenantMismatchError("Access to the requested data source is forbidden.")

            schema_ctx = self._build_schema_from_datasource(data_source)
            self._cache[cache_key] = (now, schema_ctx)
            return schema_ctx

        # 3. Check if datasource_id matches a Dataset
        dset_stmt = (
            select(Dataset)
            .where(Dataset.id == datasource_id)
            .options(selectinload(Dataset.columns))
        )
        dset_res = await session.execute(dset_stmt)
        dataset = dset_res.scalar_one_or_none()

        if dataset is not None:
            if dataset.organization_id != organization_id:
                logger.warning(
                    "Cross-tenant Dataset access attempt detected",
                    dataset_id=str(datasource_id),
                    requested_org=str(organization_id),
                    actual_org=str(dataset.organization_id),
                )
                raise SQLTenantMismatchError("Access to the requested dataset is forbidden.")

            if dataset.status.lower() not in ("ready", "active"):
                logger.warning(
                    "Attempted to access dataset that is not ready",
                    dataset_id=str(datasource_id),
                    status=dataset.status,
                )
                raise SQLDataSourceNotFoundError(
                    f"Dataset {datasource_id} is not in READY status (status: {dataset.status})."
                )

            schema_ctx = self._build_schema_from_dataset(dataset)
            self._cache[cache_key] = (now, schema_ctx)
            return schema_ctx

        # 4. Neither DataSource nor Dataset found
        raise SQLDataSourceNotFoundError(
            f"DataSource or Dataset {datasource_id} not found for this tenant."
        )

    def _build_schema_from_datasource(self, ds: DataSource) -> SchemaContext:
        """Construct SchemaContext from DataSource configuration or schema metadata."""
        config = ds.configuration or {}
        tables_dict: dict[str, TableSchema] = {}
        relationships: list[RelationshipSchema] = []

        # If configuration provides explicit tables definition
        raw_tables = config.get("tables", {})
        if isinstance(raw_tables, dict):
            for t_name, t_meta in raw_tables.items():
                cols: list[ColumnSchema] = []
                raw_cols = t_meta.get("columns", {})
                if isinstance(raw_cols, dict):
                    for c_name, c_meta in raw_cols.items():
                        if isinstance(c_meta, dict):
                            c_type = c_meta.get("type", "TEXT")
                            is_pk = c_meta.get("is_pk", False)
                            nullable = c_meta.get("nullable", True)
                            desc = c_meta.get("description")
                        else:
                            c_type = str(c_meta)
                            is_pk = False
                            nullable = True
                            desc = None
                        cols.append(
                            ColumnSchema(
                                name=c_name,
                                data_type=c_type,
                                nullable=nullable,
                                is_primary_key=is_pk,
                                description=desc,
                            )
                        )
                tables_dict[t_name] = TableSchema(
                    name=t_name,
                    description=t_meta.get("description"),
                    row_estimate=t_meta.get("row_count"),
                    columns=cols,
                )

        # If relationships are provided
        raw_rels = config.get("relationships", [])
        if isinstance(raw_rels, list):
            for r in raw_rels:
                if isinstance(r, dict):
                    relationships.append(
                        RelationshipSchema(
                            from_table=r.get("from_table", ""),
                            from_column=r.get("from_column", ""),
                            to_table=r.get("to_table", ""),
                            to_column=r.get("to_column", ""),
                        )
                    )

        # Fallback table if configuration has no tables
        if not tables_dict:
            clean_name = ds.name.lower().replace(" ", "_").replace("-", "_")
            tables_dict[clean_name] = TableSchema(
                name=clean_name,
                description=f"Primary table for data source {ds.name}",
                columns=[
                    ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
                    ColumnSchema(name="name", data_type="VARCHAR(255)"),
                    ColumnSchema(name="amount", data_type="NUMERIC(15,2)"),
                    ColumnSchema(name="date", data_type="DATE"),
                ],
            )

        return SchemaContext(
            datasource_id=ds.id,
            organization_id=ds.organization_id,
            dialect="postgres",
            tables=tables_dict,
            relationships=relationships,
        )

    def _build_schema_from_dataset(self, dset: Dataset) -> SchemaContext:
        """Construct SchemaContext from Dataset entity and its columns."""
        clean_table_name = dset.name.lower().replace(" ", "_").replace("-", "_")
        columns: list[ColumnSchema] = []

        for col in dset.columns:
            columns.append(
                ColumnSchema(
                    name=col.name,
                    data_type=col.data_type,
                    nullable=col.nullable,
                    is_primary_key=(col.name.lower() == "id"),
                    description=col.description,
                )
            )

        if not columns:
            columns.append(ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True))

        tables_dict = {
            clean_table_name: TableSchema(
                name=clean_table_name,
                description=dset.description,
                row_estimate=dset.row_count,
                columns=columns,
            )
        }

        return SchemaContext(
            datasource_id=dset.id,
            organization_id=dset.organization_id,
            dialect="postgres",
            tables=tables_dict,
            relationships=[],
        )
