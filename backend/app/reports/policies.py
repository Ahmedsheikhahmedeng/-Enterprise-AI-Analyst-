"""Security, tenant isolation, and input sanitization policies for reports."""

import re
import unicodedata
from uuid import UUID

from app.models.analysis import AnalysisRun
from app.models.report import Report, ReportVersion
from app.reports.exceptions import ReportAuthorizationError


class ReportSecurityPolicy:
    """Enforces tenant boundaries and prevents path traversal / untrusted injection."""

    def validate_report_access(
        self,
        report: Report | ReportVersion,
        organization_id: UUID,
    ) -> None:
        """Ensure report belongs strictly to the authenticated tenant."""
        if report.organization_id != organization_id:
            raise ReportAuthorizationError(
                message="Cross-tenant access to this report is strictly prohibited.",
                details={
                    "report_org": str(report.organization_id),
                    "tenant_org": str(organization_id),
                },
            )

    def validate_analysis_access(
        self,
        analysis_run: AnalysisRun,
        organization_id: UUID,
    ) -> None:
        """Ensure target AnalysisRun belongs strictly to the authenticated tenant."""
        if analysis_run.organization_id != organization_id:
            raise ReportAuthorizationError(
                message="Cross-tenant access to this analysis run is strictly prohibited.",
                details={
                    "analysis_org": str(analysis_run.organization_id),
                    "tenant_org": str(organization_id),
                },
            )

    @staticmethod
    def sanitize_filename(title: str, version: int, ext: str) -> str:
        """Generate a safe, directory-traversal-proof filename for exported reports."""
        ext = ext.lstrip(".").lower()
        if ext not in {"pdf", "csv", "md", "html", "json"}:
            ext = "txt"

        # Normalize unicode and slugify
        slug = unicodedata.normalize("NFKD", title)
        slug = re.sub(r"[^\w\s-]", "", slug).strip().lower()
        slug = re.sub(r"[-\s]+", "-", slug)
        if not slug:
            slug = "report"

        # Keep length bounded
        slug = slug[:80].rstrip("-")
        return f"{slug}-v{version}.{ext}"
