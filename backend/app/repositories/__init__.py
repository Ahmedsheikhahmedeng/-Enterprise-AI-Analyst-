"""Repository layer providing tenant-scoped database query isolation."""

from app.repositories.base import TenantScopedRepository
from app.repositories.document import DocumentRepository
from app.repositories.report import ReportRepository

__all__ = [
    "TenantScopedRepository",
    "DocumentRepository",
    "ReportRepository",
]
