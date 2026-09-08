"""Tenant-isolated repository for all Compliance & Security Governance entities."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.models import (
    AccessReview,
    AccessReviewItem,
    ComplianceControl,
    ComplianceEvidence,
    ControlAssessment,
    DataClassificationRecord,
    DataHandlingPolicy,
    LegalHold,
    PIIHandlingPolicy,
    PrivacyRequest,
    RetentionPolicy,
    RiskAcceptance,
    SecurityFinding,
)


class ComplianceRepository:
    """Encapsulates tenant-aware database operations across compliance tables."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Controls
    # -------------------------------------------------------------------------
    async def list_controls(
        self,
        organization_id: uuid.UUID | None = None,
        framework: str | None = None,
    ) -> list[ComplianceControl]:
        stmt = select(ComplianceControl)
        if organization_id:
            stmt = stmt.where(
                or_(
                    ComplianceControl.organization_id == organization_id,
                    ComplianceControl.organization_id.is_(None),
                )
            )
        else:
            stmt = stmt.where(ComplianceControl.organization_id.is_(None))

        if framework:
            stmt = stmt.where(ComplianceControl.framework == framework)

        stmt = stmt.order_by(ComplianceControl.control_code)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_control(
        self, control_id: str, organization_id: uuid.UUID | None = None
    ) -> ComplianceControl | None:
        stmt = select(ComplianceControl).where(ComplianceControl.id == control_id)
        if organization_id:
            stmt = stmt.where(
                or_(
                    ComplianceControl.organization_id == organization_id,
                    ComplianceControl.organization_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_control(self, control: ComplianceControl) -> ComplianceControl:
        self.db.add(control)
        await self.db.flush()
        return control

    # -------------------------------------------------------------------------
    # Assessments
    # -------------------------------------------------------------------------
    async def list_assessments(
        self, organization_id: uuid.UUID | None = None
    ) -> list[ControlAssessment]:
        stmt = select(ControlAssessment)
        if organization_id:
            stmt = stmt.where(
                or_(
                    ControlAssessment.organization_id == organization_id,
                    ControlAssessment.organization_id.is_(None),
                )
            )
        stmt = stmt.order_by(ControlAssessment.assessed_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_assessment(self, assessment: ControlAssessment) -> ControlAssessment:
        self.db.add(assessment)
        await self.db.flush()
        return assessment

    # -------------------------------------------------------------------------
    # Evidence
    # -------------------------------------------------------------------------
    async def list_evidence(
        self,
        control_id: str | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> list[ComplianceEvidence]:
        stmt = select(ComplianceEvidence)
        if organization_id:
            stmt = stmt.where(
                or_(
                    ComplianceEvidence.organization_id == organization_id,
                    ComplianceEvidence.organization_id.is_(None),
                )
            )
        if control_id:
            stmt = stmt.where(ComplianceEvidence.control_id == control_id)

        stmt = stmt.order_by(ComplianceEvidence.captured_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_evidence(self, evidence: ComplianceEvidence) -> ComplianceEvidence:
        self.db.add(evidence)
        await self.db.flush()
        return evidence

    # -------------------------------------------------------------------------
    # Data Classifications & Policies
    # -------------------------------------------------------------------------
    async def get_classification(
        self, organization_id: uuid.UUID, resource_type: str, resource_id: str
    ) -> DataClassificationRecord | None:
        stmt = select(DataClassificationRecord).where(
            DataClassificationRecord.organization_id == organization_id,
            DataClassificationRecord.resource_type == resource_type,
            DataClassificationRecord.resource_id == resource_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_classifications(
        self, organization_id: uuid.UUID
    ) -> list[DataClassificationRecord]:
        stmt = (
            select(DataClassificationRecord)
            .where(DataClassificationRecord.organization_id == organization_id)
            .order_by(DataClassificationRecord.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_classification(
        self, record: DataClassificationRecord
    ) -> DataClassificationRecord:
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_data_handling_policy(
        self, classification: str, organization_id: uuid.UUID | None = None
    ) -> DataHandlingPolicy | None:
        stmt = select(DataHandlingPolicy).where(DataHandlingPolicy.classification == classification)
        if organization_id:
            stmt = stmt.where(
                or_(
                    DataHandlingPolicy.organization_id == organization_id,
                    DataHandlingPolicy.organization_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_data_handling_policy(self, policy: DataHandlingPolicy) -> DataHandlingPolicy:
        self.db.add(policy)
        await self.db.flush()
        return policy

    # -------------------------------------------------------------------------
    # PII Policies
    # -------------------------------------------------------------------------
    async def list_pii_policies(
        self, organization_id: uuid.UUID | None = None
    ) -> list[PIIHandlingPolicy]:
        stmt = select(PIIHandlingPolicy)
        if organization_id:
            stmt = stmt.where(
                or_(
                    PIIHandlingPolicy.organization_id == organization_id,
                    PIIHandlingPolicy.organization_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_pii_policy(self, policy: PIIHandlingPolicy) -> PIIHandlingPolicy:
        self.db.add(policy)
        await self.db.flush()
        return policy

    # -------------------------------------------------------------------------
    # Retention & Legal Holds
    # -------------------------------------------------------------------------
    async def list_retention_policies(
        self, organization_id: uuid.UUID | None = None
    ) -> list[RetentionPolicy]:
        stmt = select(RetentionPolicy)
        if organization_id:
            stmt = stmt.where(
                or_(
                    RetentionPolicy.organization_id == organization_id,
                    RetentionPolicy.organization_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_retention_policy(self, policy: RetentionPolicy) -> RetentionPolicy:
        self.db.add(policy)
        await self.db.flush()
        return policy

    async def list_active_legal_holds(self, organization_id: uuid.UUID) -> list[LegalHold]:
        stmt = (
            select(LegalHold)
            .where(
                LegalHold.organization_id == organization_id,
                LegalHold.active.is_(True),
            )
            .order_by(LegalHold.starts_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_legal_hold(self, hold: LegalHold) -> LegalHold:
        self.db.add(hold)
        await self.db.flush()
        return hold

    # -------------------------------------------------------------------------
    # Access Reviews
    # -------------------------------------------------------------------------
    async def list_access_reviews(self, organization_id: uuid.UUID) -> list[AccessReview]:
        stmt = (
            select(AccessReview)
            .where(AccessReview.organization_id == organization_id)
            .order_by(AccessReview.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_access_review(self, review: AccessReview) -> AccessReview:
        self.db.add(review)
        await self.db.flush()
        return review

    async def save_access_review_item(self, item: AccessReviewItem) -> AccessReviewItem:
        self.db.add(item)
        await self.db.flush()
        return item

    # -------------------------------------------------------------------------
    # Security Findings & Risk Acceptance
    # -------------------------------------------------------------------------
    async def list_findings(
        self,
        organization_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[SecurityFinding]:
        stmt = select(SecurityFinding)
        if organization_id:
            stmt = stmt.where(
                or_(
                    SecurityFinding.organization_id == organization_id,
                    SecurityFinding.organization_id.is_(None),
                )
            )
        if status:
            stmt = stmt.where(SecurityFinding.status == status)

        stmt = stmt.order_by(SecurityFinding.first_detected_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_finding(
        self, finding_id: str, organization_id: uuid.UUID | None = None
    ) -> SecurityFinding | None:
        stmt = select(SecurityFinding).where(SecurityFinding.id == finding_id)
        if organization_id:
            stmt = stmt.where(
                or_(
                    SecurityFinding.organization_id == organization_id,
                    SecurityFinding.organization_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_finding(self, finding: SecurityFinding) -> SecurityFinding:
        self.db.add(finding)
        await self.db.flush()
        return finding

    async def list_risk_acceptances(
        self, organization_id: uuid.UUID | None = None
    ) -> list[RiskAcceptance]:
        stmt = select(RiskAcceptance)
        if organization_id:
            stmt = stmt.where(
                or_(
                    RiskAcceptance.organization_id == organization_id,
                    RiskAcceptance.organization_id.is_(None),
                )
            )
        stmt = stmt.order_by(RiskAcceptance.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_risk_acceptance(self, acceptance: RiskAcceptance) -> RiskAcceptance:
        self.db.add(acceptance)
        await self.db.flush()
        return acceptance

    # -------------------------------------------------------------------------
    # Privacy Requests
    # -------------------------------------------------------------------------
    async def list_privacy_requests(self, organization_id: uuid.UUID) -> list[PrivacyRequest]:
        stmt = (
            select(PrivacyRequest)
            .where(PrivacyRequest.organization_id == organization_id)
            .order_by(PrivacyRequest.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_privacy_request(
        self, request_id: str, organization_id: uuid.UUID
    ) -> PrivacyRequest | None:
        stmt = select(PrivacyRequest).where(
            PrivacyRequest.id == request_id,
            PrivacyRequest.organization_id == organization_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_privacy_request(self, req: PrivacyRequest) -> PrivacyRequest:
        self.db.add(req)
        await self.db.flush()
        return req
