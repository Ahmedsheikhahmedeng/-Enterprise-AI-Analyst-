"""ReportService: Central orchestrator for synthesizing, persisting, versioning,
and exporting reports.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import AnalysisRun, AnalysisStep
from app.models.audit import AuditLog
from app.models.report import Report, ReportVersion
from app.reports.builder import ReportBuilder
from app.reports.config import ReportConfig, get_report_config
from app.reports.exceptions import (
    ReportNotFoundError,
    UnsupportedExportFormatError,
)
from app.reports.exporters.csv import CSVExporter
from app.reports.models import ReportDocument, ReportStatus
from app.reports.policies import ReportSecurityPolicy
from app.reports.renderers.html import HTMLRenderer
from app.reports.renderers.markdown import MarkdownRenderer
from app.reports.renderers.pdf import PDFRenderer
from app.reports.validator import ReportValidator
from app.reports.versioning import ReportVersionManager

logger = logging.getLogger(__name__)


class ReportService:
    """Service providing end-to-end report lifecycle management."""

    def __init__(
        self,
        config: ReportConfig | None = None,
        builder: ReportBuilder | None = None,
        validator: ReportValidator | None = None,
        version_manager: ReportVersionManager | None = None,
        security_policy: ReportSecurityPolicy | None = None,
    ) -> None:
        self.config = config or get_report_config()
        self.builder = builder or ReportBuilder(config=self.config)
        self.validator = validator or ReportValidator()
        self.version_manager = version_manager or ReportVersionManager()
        self.security_policy = security_policy or ReportSecurityPolicy()

        self.markdown_renderer = MarkdownRenderer()
        self.html_renderer = HTMLRenderer()
        self.pdf_renderer = PDFRenderer()
        self.csv_exporter = CSVExporter()

    async def create_report_from_analysis(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        title: str,
        user_id: UUID | None = None,
        subtitle: str | None = None,
        template: str = "executive",
    ) -> tuple[Report, ReportVersion, ReportDocument]:
        """Create and persist a new report from an existing completed AnalysisRun."""
        # 1. Fetch AnalysisRun with steps
        stmt = (
            select(AnalysisRun)
            .where(AnalysisRun.id == analysis_run_id)
            .options(selectinload(AnalysisRun.steps))
        )
        res = await session.execute(stmt)
        analysis_run = res.scalars().first()

        if not analysis_run:
            raise ReportNotFoundError(
                message="AnalysisRun not found for report generation.",
                details={"analysis_run_id": str(analysis_run_id)},
            )

        # 2. Enforce tenant ownership
        self.security_policy.validate_analysis_access(analysis_run, organization_id)

        # 3. Extract analyst synthesis output payload
        synthesis_step: AnalysisStep | None = None
        sql_step: AnalysisStep | None = None

        for step in analysis_run.steps:
            if step.step_type == "analyst_synthesis":
                synthesis_step = step
            elif step.step_type == "sql_agent":
                sql_step = step

        payload: dict[str, Any] = (synthesis_step.output_payload or {}) if synthesis_step else {}
        answer = payload.get("answer") or ""
        confidence = float(payload.get("confidence", 1.0))
        evidence = payload.get("evidence") or []
        conflicts = payload.get("conflicts") or []
        citations = payload.get("citations") or []
        diagnostics = payload.get("diagnostics") or {}

        # Structured SQL results
        sql_rows: list[dict[str, Any]] = []
        sql_metrics: dict[str, Any] = {}
        if sql_step and sql_step.output_payload:
            sql_out = sql_step.output_payload
            sql_rows = sql_out.get("rows") or []
            analysis_dict = sql_out.get("analysis") or {}
            sql_metrics = analysis_dict.get("metrics") or {}

        if not sql_rows:
            sql_rows = payload.get("sql_rows") or []
        if not sql_metrics:
            sql_metrics = payload.get("sql_metrics") or {}

        if not sql_rows:
            rows_from_ev = [
                ev["metadata"]["row"]
                for ev in evidence
                if isinstance(ev.get("metadata"), dict) and "row" in ev["metadata"]
            ]
            if rows_from_ev:
                sql_rows = rows_from_ev

        if not sql_metrics:
            for ev in evidence:
                if isinstance(ev.get("metadata"), dict) and "metrics" in ev["metadata"]:
                    sql_metrics.update(ev["metadata"]["metrics"])

        # 4. Build ReportDocument
        doc = self.builder.build_from_analysis_context(
            title=title,
            subtitle=subtitle,
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            user_id=user_id,
            query=analysis_run.query,
            answer=answer,
            confidence=confidence,
            evidence_list=evidence,
            conflicts_list=conflicts,
            citations_list=citations,
            diagnostics=diagnostics,
            sql_rows=sql_rows,
            sql_metrics=sql_metrics,
            template=template,
            version=1,
            status=ReportStatus.DRAFT,
        )

        # 5. Validate ReportDocument
        self.validator.validate(doc)

        # 6. Render initial content
        rendered_content = self.markdown_renderer.render(doc)

        # 7. Create root Report record
        now = datetime.now(UTC)
        report = Report(
            id=doc.report_id,
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            created_by=user_id,
            title=doc.title,
            status=ReportStatus.DRAFT.value,
            current_version=1,
            content=rendered_content,
            content_hash=doc.content_hash,
            metadata_=doc.to_dict(),
            created_at=now,
            updated_at=now,
        )
        session.add(report)
        await session.flush()

        # 8. Create version 1 record
        version_rec = ReportVersion(
            id=uuid4(),
            report_id=report.id,
            organization_id=organization_id,
            version_number=1,
            title=doc.title,
            status=ReportStatus.DRAFT.value,
            content=rendered_content,
            document_data=doc.to_dict(),
            content_hash=doc.content_hash,
            created_by=user_id,
            created_at=now,
        )
        session.add(version_rec)

        # 9. Audit event
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="report.created",
            resource_type="report",
            resource_id=str(report.id),
            metadata_={
                "title": doc.title,
                "version": 1,
                "content_hash": doc.content_hash,
                "analysis_run_id": str(analysis_run_id),
            },
        )
        session.add(audit)
        await session.commit()
        await session.refresh(report)
        await session.refresh(version_rec)

        logger.info(
            "Created enterprise report %s (v1) for org %s",
            report.id,
            organization_id,
        )
        return report, version_rec, doc

    async def get_report(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        report_id: UUID,
        version_number: int | None = None,
        user_id: UUID | None = None,
        record_audit: bool = True,
    ) -> tuple[Report, ReportVersion, ReportDocument]:
        """Fetch report and specific (or current) version, enforcing tenant isolation."""
        stmt = select(Report).where(Report.id == report_id)
        res = await session.execute(stmt)
        report = res.scalars().first()

        if not report:
            raise ReportNotFoundError(
                message=f"Report with id '{report_id}' not found.",
                details={"report_id": str(report_id)},
            )

        self.security_policy.validate_report_access(report, organization_id)

        target_version = version_number or report.current_version
        v_stmt = select(ReportVersion).where(
            ReportVersion.report_id == report_id,
            ReportVersion.version_number == target_version,
        )
        v_res = await session.execute(v_stmt)
        version_rec = v_res.scalars().first()

        if not version_rec:
            raise ReportNotFoundError(
                message=f"Version {target_version} of report '{report_id}' not found.",
                details={"report_id": str(report_id), "version": target_version},
            )

        doc = ReportDocument.from_dict(version_rec.document_data)

        if record_audit:
            audit = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="report.viewed",
                resource_type="report",
                resource_id=str(report_id),
                metadata_={"version": target_version},
            )
            session.add(audit)
            await session.commit()

        return report, version_rec, doc

    async def list_reports(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[Report], int]:
        """List reports scoped strictly to authenticated tenant with pagination."""
        offset = max(page - 1, 0) * page_size

        count_stmt = select(func.count(Report.id)).where(Report.organization_id == organization_id)
        query_stmt = select(Report).where(Report.organization_id == organization_id)

        if status:
            count_stmt = count_stmt.where(Report.status == status)
            query_stmt = query_stmt.where(Report.status == status)

        query_stmt = query_stmt.order_by(Report.created_at.desc()).offset(offset).limit(page_size)

        total_res = await session.execute(count_stmt)
        total_count = total_res.scalar() or 0

        items_res = await session.execute(query_stmt)
        reports = list(items_res.scalars().all())

        return reports, total_count

    async def publish_report(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        report_id: UUID,
        version_number: int | None = None,
        user_id: UUID | None = None,
    ) -> tuple[Report, ReportVersion, ReportDocument]:
        """Publish an active or specified version of a report, rendering it immutable."""
        stmt = select(Report).where(Report.id == report_id)
        res = await session.execute(stmt)
        report = res.scalars().first()

        if not report:
            raise ReportNotFoundError(
                message=f"Report with id '{report_id}' not found.",
                details={"report_id": str(report_id)},
            )

        self.security_policy.validate_report_access(report, organization_id)

        version_rec = await self.version_manager.publish_version(
            session=session,
            report=report,
            version_number=version_number,
            user_id=user_id,
        )

        doc = ReportDocument.from_dict(version_rec.document_data)

        # Audit
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="report.published",
            resource_type="report",
            resource_id=str(report_id),
            metadata_={
                "version": version_rec.version_number,
                "content_hash": version_rec.content_hash,
            },
        )
        session.add(audit)
        await session.commit()
        await session.refresh(report)
        await session.refresh(version_rec)

        logger.info("Published report %s (v%s)", report.id, version_rec.version_number)
        return report, version_rec, doc

    async def archive_report(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        report_id: UUID,
        user_id: UUID | None = None,
    ) -> Report:
        """Mark report status as archived."""
        stmt = select(Report).where(Report.id == report_id)
        res = await session.execute(stmt)
        report = res.scalars().first()

        if not report:
            raise ReportNotFoundError(
                message=f"Report with id '{report_id}' not found.",
                details={"report_id": str(report_id)},
            )

        self.security_policy.validate_report_access(report, organization_id)

        report.status = ReportStatus.ARCHIVED.value
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="report.archived",
            resource_type="report",
            resource_id=str(report_id),
        )
        session.add(audit)
        await session.commit()
        await session.refresh(report)

        logger.info("Archived report %s", report.id)
        return report

    async def export_report(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        report_id: UUID,
        export_format: str,
        version_number: int | None = None,
        table_id: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[str | bytes, str, str]:
        """Export report in requested format, returning (content, filename, media_type)."""
        report, version_rec, doc = await self.get_report(
            session=session,
            organization_id=organization_id,
            report_id=report_id,
            version_number=version_number,
            user_id=user_id,
            record_audit=False,
        )

        fmt = export_format.lower().strip()
        filename = self.security_policy.sanitize_filename(
            title=doc.title,
            version=doc.version,
            ext=fmt,
        )

        content: str | bytes
        media_type: str

        if fmt in {"md", "markdown"}:
            content = self.markdown_renderer.render(doc)
            media_type = "text/markdown; charset=utf-8"
        elif fmt == "html":
            content = self.html_renderer.render(doc)
            media_type = "text/html; charset=utf-8"
        elif fmt == "pdf":
            content = self.pdf_renderer.render(doc)
            media_type = "application/pdf"
        elif fmt == "csv":
            content = self.csv_exporter.export(doc, table_id=table_id)
            media_type = "text/csv; charset=utf-8"
        else:
            raise UnsupportedExportFormatError(format_name=fmt)

        # Audit export action
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="report.exported",
            resource_type="report",
            resource_id=str(report_id),
            metadata_={
                "version": doc.version,
                "format": fmt,
                "filename": filename,
            },
        )
        session.add(audit)
        await session.commit()

        return content, filename, media_type
