"""Security, tenant isolation, and RBAC policy validation for the Analyst subsystem."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.exceptions import AnalystTenantMismatchError
from app.models.data_source import DataSource


class AnalystSecurityPolicy:
    """Enforces server-side tenant isolation, RBAC permissions, and datasource boundaries."""

    @staticmethod
    async def validate_datasource_access(
        datasource_id: UUID,
        organization_id: UUID,
        session: AsyncSession,
    ) -> DataSource:
        """Verify that the targeted datasource belongs strictly to the authenticated tenant."""
        stmt = select(DataSource).where(
            DataSource.id == datasource_id,
            DataSource.organization_id == organization_id,
        )
        res = await session.execute(stmt)
        ds = res.scalar_one_or_none()
        if ds is None:
            msg = f"Datasource {datasource_id} does not exist or does not belong to your org."
            raise AnalystTenantMismatchError(
                message=msg,
                details={
                    "datasource_id": str(datasource_id),
                    "organization_id": str(organization_id),
                },
            )
        return ds
