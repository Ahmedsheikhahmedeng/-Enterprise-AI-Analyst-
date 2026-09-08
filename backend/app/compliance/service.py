"""High-level service orchestrating Compliance Assessments, Posture, Privacy, and Evidence."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.access_reviews import AccessReviewEngine
from app.compliance.assessor import ComplianceAssessor
from app.compliance.audit_integrity import AuditIntegrityVerifier
from app.compliance.control_catalog import GLOBAL_CONTROL_CATALOG
from app.compliance.enums import (
    AccessReviewStatus,
    ControlSeverity,
    FindingStatus,
    PrivacyRequestStatus,
    PrivacyRequestType,
)
from app.compliance.evidence import EvidenceEngine
from app.compliance.exceptions import (
    ComplianceError,
    UnapprovedRiskAcceptanceError,
)
from app.compliance.models import (
    AccessReview,
    AccessReviewItem,
    ComplianceControl,
    ComplianceEvidence,
    ControlAssessment,
    PrivacyRequest,
    RiskAcceptance,
)
from app.compliance.posture import SecurityPostureEngine
from app.compliance.readiness import ComplianceReadinessEvaluator
from app.compliance.repository import ComplianceRepository
from app.compliance.schemas import (
    AccessReviewResponse,
    ComplianceControlResponse,
    ComplianceEvidenceResponse,
    ComplianceOverviewResponse,
    ComplianceReadinessResponse,
    ControlAssessmentResponse,
    PillarPosture,
    PrivacyRequestResponse,
    RiskAcceptanceResponse,
    SecurityPostureResponse,
)


class ComplianceService:
    """Coordinates enterprise security controls, posture synthesis, and governance enforcement."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ComplianceRepository(db)

    # -------------------------------------------------------------------------
    # Baseline Controls Seeding & Retrieval
    # -------------------------------------------------------------------------
    async def seed_canonical_controls(self) -> int:
        """Seed 23 canonical baseline controls into PostgreSQL if not already present."""
        existing = await self.repo.list_controls(organization_id=None)
        existing_ids = {c.id for c in existing}

        seeded = 0
        now = datetime.now(UTC)
        for definition in GLOBAL_CONTROL_CATALOG.list_all():
            if definition.id not in existing_ids:
                control = ComplianceControl(
                    id=definition.id,
                    organization_id=None,
                    framework=definition.framework.value,
                    control_code=definition.control_code,
                    name=definition.name,
                    description=definition.description,
                    category=definition.category.value,
                    severity=definition.severity.value,
                    automated=definition.automated,
                    enabled=True,
                    version=1,
                    parameters=definition.parameters,
                    created_at=now,
                    updated_at=now,
                )
                await self.repo.save_control(control)
                existing_ids.add(definition.id)
                seeded += 1
        return seeded

    async def list_controls(
        self,
        organization_id: uuid.UUID | None = None,
        framework: str | None = None,
    ) -> list[ComplianceControlResponse]:
        await self.seed_canonical_controls()
        controls = await self.repo.list_controls(
            organization_id=organization_id, framework=framework
        )
        assessments = await self.repo.list_assessments(organization_id=organization_id)
        latest_assessment_by_ctrl = {}
        for a in assessments:
            if a.control_id not in latest_assessment_by_ctrl:
                latest_assessment_by_ctrl[a.control_id] = {
                    "status": a.status,
                    "score": a.score,
                    "assessed_at": a.assessed_at.isoformat(),
                    "reason": a.reason,
                }

        results = []
        for c in controls:
            dto = ComplianceControlResponse.model_validate(c)
            dto.latest_assessment = latest_assessment_by_ctrl.get(c.id)
            results.append(dto)
        return results

    # -------------------------------------------------------------------------
    # Continuous Assessment Execution
    # -------------------------------------------------------------------------
    async def run_assessment(
        self,
        organization_id: uuid.UUID | None = None,
        control_id: str | None = None,
    ) -> list[ControlAssessmentResponse]:
        """Perform continuous compliance assessment over active evidence and security findings."""
        await self.seed_canonical_controls()
        controls = await self.repo.list_controls(organization_id=organization_id)
        if control_id:
            controls = [c for c in controls if c.id == control_id]

        evidence_items = await self.repo.list_evidence(organization_id=organization_id)
        findings = await self.repo.list_findings(organization_id=organization_id)

        evidence_by_ctrl: dict[str, list[dict[str, Any]]] = {}
        for e in evidence_items:
            evidence_by_ctrl.setdefault(e.control_id, []).append(
                {
                    "evidence_type": e.evidence_type,
                    "captured_at": e.captured_at,
                    "expires_at": e.expires_at,
                    "source": e.source,
                }
            )

        findings_dicts = [
            {"id": f.id, "control_id": f.control_id, "severity": f.severity, "status": f.status}
            for f in findings
        ]

        responses = []
        now = datetime.now(UTC)
        for ctrl in controls:
            c_evidence = evidence_by_ctrl.get(ctrl.id, [])
            res = ComplianceAssessor.assess_control(
                control_id=ctrl.id,
                evidence_list=c_evidence,
                active_findings=findings_dicts,
                reference_time=now,
            )
            assessment_model = ControlAssessment(
                id=str(uuid.uuid4()),
                control_id=ctrl.id,
                organization_id=organization_id,
                status=res.status.value,
                score=res.score,
                reason=res.reason,
                assessed_at=now,
                assessor_type="CONTINUOUS_COMPLIANCE_ASSESSOR",
                evidence_count=res.evidence_count,
                details=res.details,
            )
            saved = await self.repo.save_assessment(assessment_model)
            responses.append(ControlAssessmentResponse.model_validate(saved))

        return responses

    # -------------------------------------------------------------------------
    # Evidence Ingestion
    # -------------------------------------------------------------------------
    async def ingest_evidence(
        self,
        control_id: str,
        evidence_type: str,
        source: str,
        reference: str,
        metadata_payload: dict[str, Any],
        organization_id: uuid.UUID | None = None,
        source_record_id: str | None = None,
        expires_at: datetime | None = None,
        actor: str | None = None,
    ) -> ComplianceEvidenceResponse:
        """Capture and record immutable verification evidence."""
        now = datetime.now(UTC)
        existing_evidence = await self.repo.list_evidence(
            control_id=control_id, organization_id=organization_id
        )
        next_version = len(existing_evidence) + 1

        digest = EvidenceEngine.compute_evidence_hash(
            control_id=control_id,
            evidence_type=evidence_type,
            source=source,
            reference=reference,
            metadata_payload=metadata_payload,
            captured_at=now,
        )

        model = ComplianceEvidence(
            id=str(uuid.uuid4()),
            control_id=control_id,
            organization_id=organization_id,
            evidence_type=evidence_type,
            source=source,
            reference=reference,
            hash=digest,
            version=next_version,
            captured_at=now,
            expires_at=expires_at,
            metadata_payload=metadata_payload,
            source_record_id=source_record_id,
            actor=actor,
        )
        saved = await self.repo.save_evidence(model)
        dto = ComplianceEvidenceResponse.model_validate(saved)
        dto.freshness = EvidenceEngine.evaluate_freshness(
            captured_at=saved.captured_at,
            evidence_type=saved.evidence_type,
            expires_at=saved.expires_at,
            reference_time=now,
        )
        return dto

    # -------------------------------------------------------------------------
    # Security Posture & Compliance Readiness
    # -------------------------------------------------------------------------
    async def get_security_posture(
        self, organization_id: uuid.UUID | None = None
    ) -> SecurityPostureResponse:
        """Compute live 12-pillar Security Posture summary."""
        assessments = await self.repo.list_assessments(organization_id=organization_id)
        findings = await self.repo.list_findings(organization_id=organization_id)

        a_dicts = [
            {"control_id": a.control_id, "status": a.status, "score": a.score} for a in assessments
        ]
        f_dicts = [
            {"id": f.id, "control_id": f.control_id, "severity": f.severity, "status": f.status}
            for f in findings
        ]

        now = datetime.now(UTC)
        pillars_map = SecurityPostureEngine.evaluate_posture(
            assessments=a_dicts,
            findings=f_dicts,
            reference_time=now,
        )

        scores = [p.score for p in pillars_map.values()]
        overall_score = round(sum(scores) / max(len(scores), 1), 1)

        pillars_dto = {
            k: PillarPosture(
                name=v.name,
                status=v.status,
                score=v.score,
                controls_passed=v.controls_passed,
                controls_total=v.controls_total,
                critical_findings=v.critical_findings,
                details=v.details,
            )
            for k, v in pillars_map.items()
        }

        return SecurityPostureResponse(
            organization_id=organization_id,
            overall_score=overall_score,
            evaluated_at=now,
            pillars=pillars_dto,
        )

    async def get_compliance_readiness(
        self, organization_id: uuid.UUID | None = None
    ) -> ComplianceReadinessResponse:
        """Evaluate readiness decision and blocker factors."""
        assessments = await self.repo.list_assessments(organization_id=organization_id)
        findings = await self.repo.list_findings(organization_id=organization_id)
        risk_acceptances = await self.repo.list_risk_acceptances(organization_id=organization_id)

        now = datetime.now(UTC)
        expired_ra = sum(1 for ra in risk_acceptances if now > ra.expires_at)

        a_dicts = [
            {"control_id": a.control_id, "status": a.status, "score": a.score, "reason": a.reason}
            for a in assessments
        ]
        f_dicts = [{"id": f.id, "severity": f.severity, "status": f.status} for f in findings]

        evaluation = ComplianceReadinessEvaluator.evaluate_readiness(
            assessments=a_dicts,
            findings=f_dicts,
            audit_integrity_valid=True,
            expired_risk_acceptances_count=expired_ra,
            reference_time=now,
        )

        return ComplianceReadinessResponse(
            organization_id=organization_id,
            decision=evaluation.decision,
            composite_score=evaluation.composite_score,
            framework_scores=evaluation.framework_scores,
            passed_controls=evaluation.passed_controls,
            warning_controls=evaluation.warning_controls,
            failed_controls=evaluation.failed_controls,
            not_assessed_controls=evaluation.not_assessed_controls,
            blockers=evaluation.blockers,
            warnings=evaluation.warnings,
            evaluated_at=evaluation.evaluated_at,
        )

    async def get_overview(
        self, organization_id: uuid.UUID | None = None
    ) -> ComplianceOverviewResponse:
        """Provide unified high-level dashboard telemetry."""
        posture = await self.get_security_posture(organization_id)
        readiness = await self.get_compliance_readiness(organization_id)
        findings = await self.repo.list_findings(organization_id=organization_id)

        open_findings = [
            f
            for f in findings
            if f.status in (FindingStatus.OPEN.value, FindingStatus.ACKNOWLEDGED.value)
        ]
        critical_findings = [
            f for f in open_findings if f.severity == ControlSeverity.CRITICAL.value
        ]

        legal_holds_count = (
            len(await self.repo.list_active_legal_holds(organization_id)) if organization_id else 0
        )
        privacy_reqs_count = (
            len(await self.repo.list_privacy_requests(organization_id)) if organization_id else 0
        )
        access_reviews_count = (
            len(await self.repo.list_access_reviews(organization_id)) if organization_id else 0
        )

        return ComplianceOverviewResponse(
            organization_id=organization_id,
            security_posture=posture,
            compliance_readiness=readiness,
            open_findings_count=len(open_findings),
            critical_findings_count=len(critical_findings),
            active_legal_holds_count=legal_holds_count,
            pending_privacy_requests_count=privacy_reqs_count,
            pending_access_reviews_count=access_reviews_count,
            last_assessment_time=readiness.evaluated_at,
        )

    # -------------------------------------------------------------------------
    # Risk Acceptance Workflow
    # -------------------------------------------------------------------------
    async def accept_finding_risk(
        self,
        finding_id: str,
        reason: str,
        expires_at: datetime,
        accepted_by: str,
        organization_id: uuid.UUID | None = None,
        privileged_approval_id: str | None = None,
    ) -> RiskAcceptanceResponse:
        """Formal risk acceptance with privileged validation for critical findings."""
        finding = await self.repo.get_finding(finding_id, organization_id=organization_id)
        if not finding:
            raise ComplianceError(f"Security finding '{finding_id}' not found.")

        # Section 29: Critical findings require explicit privileged approval
        if finding.severity == ControlSeverity.CRITICAL.value and not privileged_approval_id:
            raise UnapprovedRiskAcceptanceError(
                "Risk acceptance for CRITICAL severity findings requires explicit privileged approval ID.",
                finding_id=finding_id,
            )

        now = datetime.now(UTC)
        acceptance = RiskAcceptance(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            finding_id=finding_id,
            accepted_by=accepted_by,
            reason=reason,
            starts_at=now,
            expires_at=expires_at,
            privileged_approval_id=privileged_approval_id,
            created_at=now,
        )
        saved = await self.repo.save_risk_acceptance(acceptance)
        finding.status = FindingStatus.ACCEPTED_RISK.value
        await self.repo.save_finding(finding)

        dto = RiskAcceptanceResponse.model_validate(saved)
        dto.is_expired = now > saved.expires_at
        return dto

    # -------------------------------------------------------------------------
    # Privacy Workflow & Right-to-Delete
    # -------------------------------------------------------------------------
    async def create_privacy_request(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        request_type: PrivacyRequestType,
        requested_by: str,
        resources: list[str],
        notes: str | None = None,
    ) -> PrivacyRequestResponse:
        """Initiate governed data subject privacy request."""
        now = datetime.now(UTC)
        req = PrivacyRequest(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            user_id=user_id,
            request_type=request_type.value,
            status=PrivacyRequestStatus.REQUESTED.value,
            requested_by=requested_by,
            resources=resources,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        saved = await self.repo.save_privacy_request(req)
        return PrivacyRequestResponse.model_validate(saved)

    async def execute_privacy_request(
        self,
        request_id: str,
        organization_id: uuid.UUID,
        governance_approval_id: str,
    ) -> PrivacyRequestResponse:
        """Transition privacy request to EXECUTED upon verifying governance approval."""
        req = await self.repo.get_privacy_request(request_id, organization_id)
        if not req:
            raise ComplianceError(f"Privacy request '{request_id}' not found.")

        # Check for active legal holds blocking this user or tenant
        legal_holds = await self.repo.list_active_legal_holds(organization_id)
        if legal_holds:
            held_res = {r for h in legal_holds for r in h.resources}
            if "*" in held_res or str(req.user_id) in held_res:
                raise ComplianceError(
                    "Cannot execute privacy deletion: Active legal hold covers target user resources."
                )

        now = datetime.now(UTC)
        req.status = PrivacyRequestStatus.EXECUTED.value
        req.governance_approval_id = governance_approval_id
        req.executed_at = now
        req.updated_at = now
        saved = await self.repo.save_privacy_request(req)
        return PrivacyRequestResponse.model_validate(saved)

    # -------------------------------------------------------------------------
    # Access Review Campaigns
    # -------------------------------------------------------------------------
    async def start_access_review(
        self,
        organization_id: uuid.UUID,
        title: str,
        initiated_by: str,
        users_sample: list[dict[str, Any]],
    ) -> AccessReviewResponse:
        """Create and populate a periodic access review campaign."""
        now = datetime.now(UTC)
        review = AccessReview(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            title=title,
            initiated_by=initiated_by,
            status=AccessReviewStatus.PENDING.value,
            total_users_reviewed=len(users_sample),
            flagged_inactive_count=0,
            created_at=now,
        )
        saved_review = await self.repo.save_access_review(review)

        inactive_count = 0
        items_dto = []
        for u in users_sample:
            last_active = u.get("last_activity_at")
            evaluated = AccessReviewEngine.evaluate_user_access(
                user_id=str(u["id"]),
                user_email=u["email"],
                role=u.get("role", "Viewer"),
                permissions=u.get("permissions", []),
                last_activity_at=last_active,
                reference_time=now,
            )
            if evaluated.is_inactive:
                inactive_count += 1

            item = AccessReviewItem(
                id=str(uuid.uuid4()),
                review_id=saved_review.id,
                organization_id=organization_id,
                user_id=u["id"],
                user_email=u["email"],
                role=evaluated.role,
                permissions=evaluated.permissions,
                last_activity_at=evaluated.last_activity_at,
                granted_at=u.get("created_at", now),
                review_status=evaluated.review_status.value,
                recommendation=evaluated.recommendation,
            )
            saved_item = await self.repo.save_access_review_item(item)
            items_dto.append(saved_item)

        saved_review.flagged_inactive_count = inactive_count
        await self.repo.save_access_review(saved_review)
        return AccessReviewResponse.model_validate(saved_review)

    # -------------------------------------------------------------------------
    # Audit Integrity Check
    # -------------------------------------------------------------------------
    async def verify_audit_integrity(
        self, organization_id: uuid.UUID, audit_events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Verify sequential SHA-256 hash chains across audit logs."""
        result = AuditIntegrityVerifier.verify_ledger(
            organization_id=str(organization_id),
            events=audit_events,
        )
        return {
            "status": result.status.value,
            "total_records_checked": result.total_records_checked,
            "first_tampered_record_id": result.first_tampered_record_id,
            "reason": result.reason,
            "chain_root": result.chain_root,
            "latest_block_hash": result.latest_block_hash,
        }
