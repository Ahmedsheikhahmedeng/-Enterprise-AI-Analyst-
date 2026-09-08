"""FastAPI router implementing Enterprise Security & Compliance Governance REST endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.compliance.enums import ComplianceFramework
from app.compliance.exceptions import ComplianceError, UnapprovedRiskAcceptanceError
from app.compliance.models import (
    ComplianceControl,
    DataClassificationRecord,
    DataHandlingPolicy,
    LegalHold,
    RetentionPolicy,
    SecurityFinding,
)
from app.compliance.schemas import (
    AccessReviewCreate,
    AccessReviewResponse,
    ComplianceControlCreate,
    ComplianceControlResponse,
    ComplianceEvidenceCreate,
    ComplianceEvidenceResponse,
    ComplianceOverviewResponse,
    ComplianceReadinessResponse,
    ControlAssessmentResponse,
    DataClassificationCreate,
    DataClassificationResponse,
    DataHandlingPolicyResponse,
    DataHandlingPolicyUpsert,
    LegalHoldCreate,
    LegalHoldResponse,
    PrivacyRequestCreate,
    PrivacyRequestResponse,
    RetentionPolicyResponse,
    RetentionPolicyUpsert,
    RiskAcceptanceCreate,
    RiskAcceptanceResponse,
    SecurityFindingCreate,
    SecurityFindingResponse,
    SecurityPostureResponse,
)
from app.compliance.service import ComplianceService
from app.db.postgres import get_db_session
from app.models.user import User
from app.rbac.dependencies import require_permission
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/compliance", tags=["Enterprise Compliance & Governance"])


# ---------------------------------------------------------------------------
# Overview, Posture & Readiness
# ---------------------------------------------------------------------------
@router.get(
    "/overview",
    response_model=ComplianceOverviewResponse,
    summary="Get unified compliance and security posture overview",
    dependencies=[Depends(require_permission("compliance.read"))],
)
async def get_compliance_overview(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComplianceOverviewResponse:
    service = ComplianceService(db)
    return await service.get_overview(organization_id=tenant.organization_id)


@router.get(
    "/posture",
    response_model=SecurityPostureResponse,
    summary="Get 12-pillar Security Posture summary",
    dependencies=[Depends(require_permission("compliance.read"))],
)
async def get_security_posture(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SecurityPostureResponse:
    service = ComplianceService(db)
    return await service.get_security_posture(organization_id=tenant.organization_id)


@router.get(
    "/readiness",
    response_model=ComplianceReadinessResponse,
    summary="Get compliance release readiness decision and blockers",
    dependencies=[Depends(require_permission("compliance.read"))],
)
async def get_compliance_readiness(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComplianceReadinessResponse:
    service = ComplianceService(db)
    return await service.get_compliance_readiness(organization_id=tenant.organization_id)


# ---------------------------------------------------------------------------
# Controls Catalog & Assessment
# ---------------------------------------------------------------------------
@router.get(
    "/controls",
    response_model=list[ComplianceControlResponse],
    summary="List security and compliance controls with status",
    dependencies=[Depends(require_permission("compliance.read"))],
)
async def list_controls(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    framework: ComplianceFramework | None = None,
) -> list[ComplianceControlResponse]:
    service = ComplianceService(db)
    fw_val = framework.value if framework else None
    return await service.list_controls(organization_id=tenant.organization_id, framework=fw_val)


@router.get(
    "/controls/{control_id}",
    response_model=ComplianceControlResponse,
    summary="Get single control definition and latest assessment",
    dependencies=[Depends(require_permission("compliance.read"))],
)
async def get_control(
    control_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComplianceControlResponse:
    service = ComplianceService(db)
    ctrl = await service.repo.get_control(control_id, organization_id=tenant.organization_id)
    if not ctrl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Control '{control_id}' not found."
        )
    assessments = await service.repo.list_assessments(organization_id=tenant.organization_id)
    ctrl_assessment = next((a for a in assessments if a.control_id == control_id), None)

    dto = ComplianceControlResponse.model_validate(ctrl)
    if ctrl_assessment:
        dto.latest_assessment = {
            "status": ctrl_assessment.status,
            "score": ctrl_assessment.score,
            "assessed_at": ctrl_assessment.assessed_at.isoformat(),
            "reason": ctrl_assessment.reason,
        }
    return dto


@router.post(
    "/controls",
    response_model=ComplianceControlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register custom organization control",
    dependencies=[Depends(require_permission("compliance.manage"))],
)
async def create_control(
    payload: ComplianceControlCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComplianceControlResponse:
    service = ComplianceService(db)
    existing = await service.repo.get_control(payload.id, organization_id=tenant.organization_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Control '{payload.id}' already exists."
        )

    control = ComplianceControl(
        id=payload.id,
        organization_id=tenant.organization_id,
        framework=payload.framework.value,
        control_code=payload.control_code,
        name=payload.name,
        description=payload.description,
        category=payload.category.value,
        severity=payload.severity.value,
        automated=payload.automated,
        enabled=payload.enabled,
        version=1,
        parameters=payload.parameters,
    )
    saved = await service.repo.save_control(control)
    return ComplianceControlResponse.model_validate(saved)


@router.post(
    "/assess",
    response_model=list[ControlAssessmentResponse],
    summary="Trigger continuous assessment over controls and evidence",
    dependencies=[Depends(require_permission("compliance.assess"))],
)
async def trigger_assessment(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    control_id: Annotated[
        str | None, Query(description="Optional single control ID to assess")
    ] = None,
) -> list[ControlAssessmentResponse]:
    service = ComplianceService(db)
    return await service.run_assessment(
        organization_id=tenant.organization_id, control_id=control_id
    )


# ---------------------------------------------------------------------------
# Evidence Store
# ---------------------------------------------------------------------------
@router.get(
    "/evidence",
    response_model=list[ComplianceEvidenceResponse],
    summary="List immutable compliance verification evidence",
    dependencies=[Depends(require_permission("compliance.evidence.read"))],
)
async def list_evidence(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    control_id: str | None = None,
) -> list[ComplianceEvidenceResponse]:
    service = ComplianceService(db)
    evidence_items = await service.repo.list_evidence(
        control_id=control_id, organization_id=tenant.organization_id
    )
    return [ComplianceEvidenceResponse.model_validate(e) for e in evidence_items]


@router.post(
    "/evidence",
    response_model=ComplianceEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest new immutable compliance evidence record",
    dependencies=[Depends(require_permission("compliance.evidence.manage"))],
)
async def ingest_evidence(
    payload: ComplianceEvidenceCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComplianceEvidenceResponse:
    service = ComplianceService(db)
    return await service.ingest_evidence(
        control_id=payload.control_id,
        evidence_type=payload.evidence_type.value,
        source=payload.source,
        reference=payload.reference,
        metadata_payload=payload.metadata_payload,
        organization_id=tenant.organization_id,
        source_record_id=payload.source_record_id,
        expires_at=payload.expires_at,
        actor=user.email,
    )


# ---------------------------------------------------------------------------
# Security Findings & Risk Acceptance
# ---------------------------------------------------------------------------
@router.get(
    "/findings",
    response_model=list[SecurityFindingResponse],
    summary="List security vulnerability findings",
    dependencies=[Depends(require_permission("compliance.findings.read"))],
)
async def list_findings(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[SecurityFindingResponse]:
    service = ComplianceService(db)
    findings = await service.repo.list_findings(
        organization_id=tenant.organization_id, status=status_filter
    )
    risk_acceptances = await service.repo.list_risk_acceptances(
        organization_id=tenant.organization_id
    )
    ra_by_finding: dict[str, list[RiskAcceptanceResponse]] = {}
    for ra in risk_acceptances:
        ra_by_finding.setdefault(ra.finding_id, []).append(
            RiskAcceptanceResponse.model_validate(ra)
        )

    results = []
    for f in findings:
        dto = SecurityFindingResponse.model_validate(f)
        dto.risk_acceptances = ra_by_finding.get(f.id, [])
        results.append(dto)
    return results


@router.post(
    "/findings",
    response_model=SecurityFindingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record security vulnerability finding",
    dependencies=[Depends(require_permission("compliance.findings.manage"))],
)
async def create_finding(
    payload: SecurityFindingCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SecurityFindingResponse:
    service = ComplianceService(db)
    finding = SecurityFinding(
        id=str(uuid.uuid4()),
        organization_id=tenant.organization_id,
        control_id=payload.control_id,
        severity=payload.severity.value,
        status="OPEN",
        title=payload.title,
        description=payload.description,
        source=payload.source,
        owner=payload.owner,
        details=payload.details,
    )
    saved = await service.repo.save_finding(finding)
    return SecurityFindingResponse.model_validate(saved)


@router.post(
    "/findings/{finding_id}/risk-acceptance",
    response_model=RiskAcceptanceResponse,
    summary="Accept risk for a security finding with expiration",
    dependencies=[Depends(require_permission("compliance.risk_acceptance"))],
)
async def accept_finding_risk(
    finding_id: str,
    payload: RiskAcceptanceCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RiskAcceptanceResponse:
    service = ComplianceService(db)
    try:
        return await service.accept_finding_risk(
            finding_id=finding_id,
            reason=payload.reason,
            expires_at=payload.expires_at,
            accepted_by=user.email,
            organization_id=tenant.organization_id,
            privileged_approval_id=payload.privileged_approval_id,
        )
    except UnapprovedRiskAcceptanceError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err.message) from err
    except ComplianceError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message) from err


# ---------------------------------------------------------------------------
# Data Classification & Handling Policies
# ---------------------------------------------------------------------------
@router.get(
    "/data-classification",
    response_model=list[DataClassificationResponse],
    summary="List data classifications across datasets and documents",
    dependencies=[Depends(require_permission("compliance.read"))],
)
async def list_data_classifications(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DataClassificationResponse]:
    service = ComplianceService(db)
    records = await service.repo.list_classifications(organization_id=tenant.organization_id)
    return [DataClassificationResponse.model_validate(r) for r in records]


@router.post(
    "/data-classification",
    response_model=DataClassificationResponse,
    summary="Set or update classification tier for a resource",
    dependencies=[Depends(require_permission("compliance.manage"))],
)
async def set_data_classification(
    payload: DataClassificationCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataClassificationResponse:
    service = ComplianceService(db)
    existing = await service.repo.get_classification(
        tenant.organization_id, payload.resource_type, payload.resource_id
    )
    if existing:
        existing.classification = payload.classification.value
        existing.pii_types_detected = [p.value for p in payload.pii_types_detected]
        existing.notes = payload.notes
        existing.classified_by = user.email
        saved = await service.repo.save_classification(existing)
    else:
        record = DataClassificationRecord(
            id=str(uuid.uuid4()),
            organization_id=tenant.organization_id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            classification=payload.classification.value,
            pii_types_detected=[p.value for p in payload.pii_types_detected],
            classified_by=user.email,
            notes=payload.notes,
        )
        saved = await service.repo.save_classification(record)
    return DataClassificationResponse.model_validate(saved)


@router.post(
    "/data-handling-policy",
    response_model=DataHandlingPolicyResponse,
    summary="Configure handling policy for a classification tier",
    dependencies=[Depends(require_permission("compliance.manage"))],
)
async def upsert_data_handling_policy(
    payload: DataHandlingPolicyUpsert,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DataHandlingPolicyResponse:
    service = ComplianceService(db)
    existing = await service.repo.get_data_handling_policy(
        payload.classification.value, organization_id=tenant.organization_id
    )
    if existing:
        existing.allowed_models = payload.allowed_models
        existing.allowed_providers = payload.allowed_providers
        existing.allow_external_processing = payload.allow_external_processing
        existing.allow_export = payload.allow_export
        existing.allow_agent_usage = payload.allow_agent_usage
        existing.allow_embedding = payload.allow_embedding
        existing.retention_days = payload.retention_days
        saved = await service.repo.save_data_handling_policy(existing)
    else:
        policy = DataHandlingPolicy(
            id=str(uuid.uuid4()),
            organization_id=tenant.organization_id,
            classification=payload.classification.value,
            allowed_models=payload.allowed_models,
            allowed_providers=payload.allowed_providers,
            allow_external_processing=payload.allow_external_processing,
            allow_export=payload.allow_export,
            allow_agent_usage=payload.allow_agent_usage,
            allow_embedding=payload.allow_embedding,
            retention_days=payload.retention_days,
        )
        saved = await service.repo.save_data_handling_policy(policy)
    return DataHandlingPolicyResponse.model_validate(saved)


# ---------------------------------------------------------------------------
# Retention & Legal Holds
# ---------------------------------------------------------------------------
@router.get(
    "/retention",
    response_model=list[RetentionPolicyResponse],
    summary="List organization retention schedules",
    dependencies=[Depends(require_permission("compliance.read"))],
)
async def list_retention_policies(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RetentionPolicyResponse]:
    service = ComplianceService(db)
    policies = await service.repo.list_retention_policies(organization_id=tenant.organization_id)
    return [RetentionPolicyResponse.model_validate(p) for p in policies]


@router.post(
    "/retention",
    response_model=RetentionPolicyResponse,
    summary="Set retention duration and rules for resource type",
    dependencies=[Depends(require_permission("compliance.retention.manage"))],
)
async def upsert_retention_policy(
    payload: RetentionPolicyUpsert,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RetentionPolicyResponse:
    service = ComplianceService(db)
    policies = await service.repo.list_retention_policies(organization_id=tenant.organization_id)
    existing = next((p for p in policies if p.resource_type == payload.resource_type.value), None)
    if existing:
        existing.retention_days = payload.retention_days
        existing.legal_hold_exempt = payload.legal_hold_exempt
        existing.delete_after = payload.delete_after
        existing.enabled = payload.enabled
        saved = await service.repo.save_retention_policy(existing)
    else:
        policy = RetentionPolicy(
            id=str(uuid.uuid4()),
            organization_id=tenant.organization_id,
            resource_type=payload.resource_type.value,
            retention_days=payload.retention_days,
            legal_hold_exempt=payload.legal_hold_exempt,
            delete_after=payload.delete_after,
            enabled=payload.enabled,
        )
        saved = await service.repo.save_retention_policy(policy)
    return RetentionPolicyResponse.model_validate(saved)


@router.post(
    "/legal-holds",
    response_model=LegalHoldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Legal Hold freezing deletion eligibility",
    dependencies=[Depends(require_permission("compliance.manage"))],
)
async def create_legal_hold(
    payload: LegalHoldCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LegalHoldResponse:
    service = ComplianceService(db)
    hold = LegalHold(
        id=str(uuid.uuid4()),
        organization_id=tenant.organization_id,
        name=payload.name,
        reason=payload.reason,
        created_by=user.email,
        active=True,
        starts_at=payload.starts_at or datetime.now(UTC),
        ends_at=payload.ends_at,
        resources=payload.resources,
    )
    saved = await service.repo.save_legal_hold(hold)
    return LegalHoldResponse.model_validate(saved)


# ---------------------------------------------------------------------------
# Access Reviews
# ---------------------------------------------------------------------------
@router.get(
    "/access-reviews",
    response_model=list[AccessReviewResponse],
    summary="List historical and active access review campaigns",
    dependencies=[Depends(require_permission("compliance.access_review"))],
)
async def list_access_reviews(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AccessReviewResponse]:
    service = ComplianceService(db)
    reviews = await service.repo.list_access_reviews(organization_id=tenant.organization_id)
    return [AccessReviewResponse.model_validate(r) for r in reviews]


@router.post(
    "/access-reviews",
    response_model=AccessReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate access review campaign across organization accounts",
    dependencies=[Depends(require_permission("compliance.access_review"))],
)
async def create_access_review(
    payload: AccessReviewCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AccessReviewResponse:
    service = ComplianceService(db)
    sample = [
        {
            "id": str(tenant.user_id),
            "email": user.email,
            "role": tenant.role_name,
            "permissions": list(tenant.permissions),
            "last_activity_at": datetime.now(UTC),
        }
    ]
    return await service.start_access_review(
        organization_id=tenant.organization_id,
        title=payload.title,
        initiated_by=user.email,
        users_sample=sample,
    )


# ---------------------------------------------------------------------------
# Privacy Requests (Right-to-Delete)
# ---------------------------------------------------------------------------
@router.get(
    "/privacy-requests",
    response_model=list[PrivacyRequestResponse],
    summary="List data subject privacy requests",
    dependencies=[Depends(require_permission("compliance.privacy.manage"))],
)
async def list_privacy_requests(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PrivacyRequestResponse]:
    service = ComplianceService(db)
    reqs = await service.repo.list_privacy_requests(organization_id=tenant.organization_id)
    return [PrivacyRequestResponse.model_validate(r) for r in reqs]


@router.post(
    "/privacy-requests",
    response_model=PrivacyRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit data subject privacy request (Right-to-Delete)",
    dependencies=[Depends(require_permission("compliance.privacy.manage"))],
)
async def create_privacy_request(
    payload: PrivacyRequestCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PrivacyRequestResponse:
    service = ComplianceService(db)
    return await service.create_privacy_request(
        organization_id=tenant.organization_id,
        user_id=payload.user_id,
        request_type=payload.request_type,
        requested_by=user.email,
        resources=payload.resources,
        notes=payload.notes,
    )
