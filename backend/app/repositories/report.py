"""Tenant-scoped repository for Report entities."""

from app.models.report import Report
from app.repositories.base import TenantScopedRepository


class ReportRepository(TenantScopedRepository[Report]):
    """Tenant-isolated repository for Report entities."""

    def __init__(self) -> None:
        super().__init__(model=Report)
