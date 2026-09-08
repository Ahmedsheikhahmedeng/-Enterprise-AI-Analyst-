"""Version management ensuring immutable published reports and traceable history."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report, ReportVersion
from app.reports.exceptions import ReportNotFoundError, ReportVersionConflictError
from app.reports.models import ReportDocument, ReportStatus


class ReportVersionManager:
    """Manages transactional version increments and enforces published immutability."""

    async def create_or_update_version(
        self,
        session: AsyncSession,
        report: Report,
        doc: ReportDocument,
        rendered_content: str,
        user_id: uuid.UUID | None = None,
        force_new_version: bool = False,
    ) -> ReportVersion:
        """Create a new version or update an uncommitted draft version."""
        # Query highest existing version number for this report
        stmt = (
            select(ReportVersion)
            .where(ReportVersion.report_id == report.id)
            .order_by(ReportVersion.version_number.desc())
        )
        result = await session.execute(stmt)
        latest_version = result.scalars().first()

        now = datetime.now(UTC)

        # Rule 1: If report is published or force_new_version is True, create a new version
        if (
            report.status == ReportStatus.PUBLISHED.value
            or force_new_version
            or latest_version is None
        ):
            new_version_num = (latest_version.version_number + 1) if latest_version else 1

            doc.version = new_version_num
            version_record = ReportVersion(
                report_id=report.id,
                organization_id=report.organization_id,
                version_number=new_version_num,
                title=doc.title,
                status=ReportStatus.DRAFT.value,
                content=rendered_content,
                document_data=doc.to_dict(),
                content_hash=doc.content_hash,
                created_by=user_id or report.created_by,
                created_at=now,
            )
            session.add(version_record)
            report.current_version = new_version_num
            report.status = ReportStatus.DRAFT.value
            report.title = doc.title
            report.content = rendered_content
            report.content_hash = doc.content_hash
            report.metadata_ = doc.to_dict()
            return version_record

        # Rule 2: If latest version is in draft/generated status, update it in place
        if latest_version.status == ReportStatus.PUBLISHED.value:
            msg = (
                f"Version {latest_version.version_number} is published and immutable. "
                "Create a new version."
            )
            raise ReportVersionConflictError(
                message=msg,
                details={"version": latest_version.version_number, "report_id": str(report.id)},
            )

        # Update draft version in place
        latest_version.title = doc.title
        latest_version.content = rendered_content
        latest_version.document_data = doc.to_dict()
        latest_version.content_hash = doc.content_hash
        latest_version.created_by = user_id or latest_version.created_by

        report.title = doc.title
        report.content = rendered_content
        report.content_hash = doc.content_hash
        report.metadata_ = doc.to_dict()

        return latest_version

    async def publish_version(
        self,
        session: AsyncSession,
        report: Report,
        version_number: int | None = None,
        user_id: uuid.UUID | None = None,
    ) -> ReportVersion:
        """Publish a specific or active report version, making it permanently immutable."""
        target_version_num = version_number or report.current_version

        stmt = select(ReportVersion).where(
            ReportVersion.report_id == report.id,
            ReportVersion.version_number == target_version_num,
        )
        result = await session.execute(stmt)
        version_record = result.scalars().first()

        if not version_record:
            raise ReportNotFoundError(
                message=f"Report version {target_version_num} not found.",
                details={"report_id": str(report.id), "version": target_version_num},
            )

        now = datetime.now(UTC)
        version_record.status = ReportStatus.PUBLISHED.value
        version_record.published_at = now

        # Update report status to published if current version was published
        if report.current_version == target_version_num:
            report.status = ReportStatus.PUBLISHED.value
            report.published_at = now

        # Update the document_data status field
        doc_data = dict(version_record.document_data)
        doc_data["status"] = ReportStatus.PUBLISHED.value
        doc_data["published_at"] = now.isoformat()
        version_record.document_data = doc_data
        report.metadata_ = doc_data

        return version_record

    async def get_version(
        self,
        session: AsyncSession,
        report_id: uuid.UUID,
        version_number: int,
    ) -> ReportVersion | None:
        """Retrieve a specific version record by report ID and version number."""
        stmt = select(ReportVersion).where(
            ReportVersion.report_id == report_id,
            ReportVersion.version_number == version_number,
        )
        result = await session.execute(stmt)
        return result.scalars().first()
