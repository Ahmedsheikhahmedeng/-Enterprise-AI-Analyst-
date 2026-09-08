"""Pydantic schemas for Enterprise Security & Compliance Governance API."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.compliance.enums import (
    AccessReviewStatus,
    AssessmentStatus,
    ComplianceFramework,
    ControlCategory,
    ControlSeverity,
    DataClassificationLevel,
    EvidenceFreshness,
    EvidenceType,
    FindingSeverity,
    FindingStatus,
    PIICategory,
    PIIHandlingAction,
    PrivacyRequestStatus,
    PrivacyRequestType,
    ReadinessDecision,
    RetentionResourceType,
)


# ---------------------------------------------------------------------------
# Controls & Assessments
# ---------------------------------------------------------------------------
class ComplianceControlCreate(BaseModel):
    id: str = Field(..., max_length=64)
    framework: ComplianceFramework
    control_code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=160)
    description: str
    category: ControlCategory
    severity: ControlSeverity = ControlSeverity.HIGH
    automated: bool = True
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)


class ComplianceControlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID | None = None
    framework: str
    control_code: str
    name: str
    description: str
    category: str
    severity: str
    automated: bool
    enabled: bool
    version: int
    parameters: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    latest_assessment: dict[str, Any] | None = None


class ControlAssessmentCreate(BaseModel):
    control_id: str
    status: AssessmentStatus
    score: float = Field(ge=0.0, le=100.0)
    reason: str
    assessor_type: str = "AUTOMATED_ASSESSOR"
    details: dict[str, Any] = Field(default_factory=dict)


class ControlAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    control_id: str
    organization_id: uuid.UUID | None = None
    status: AssessmentStatus
    score: float
    reason: str
    assessed_at: datetime
    assessor_type: str
    evidence_count: int
    details: dict[str, Any]


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
class ComplianceEvidenceCreate(BaseModel):
    control_id: str
    evidence_type: EvidenceType
    source: str = Field(..., max_length=120)
    reference: str = Field(..., max_length=255)
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    source_record_id: str | None = None
    expires_at: datetime | None = None


class ComplianceEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    control_id: str
    organization_id: uuid.UUID | None = None
    evidence_type: str
    source: str
    reference: str
    hash: str
    version: int
    captured_at: datetime
    expires_at: datetime | None = None
    metadata_payload: dict[str, Any]
    source_record_id: str | None = None
    actor: str | None = None
    freshness: EvidenceFreshness = EvidenceFreshness.FRESH


# ---------------------------------------------------------------------------
# Data Classification & Handling
# ---------------------------------------------------------------------------
class DataClassificationCreate(BaseModel):
    resource_type: str
    resource_id: str
    classification: DataClassificationLevel
    pii_types_detected: list[PIICategory] = Field(default_factory=list)
    notes: str | None = None


class DataClassificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    resource_type: str
    resource_id: str
    classification: str
    pii_types_detected: list[str]
    classified_by: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class DataHandlingPolicyUpsert(BaseModel):
    classification: DataClassificationLevel
    allowed_models: list[str] = Field(default_factory=list)
    allowed_providers: list[str] = Field(default_factory=list)
    allow_external_processing: bool = False
    allow_export: bool = True
    allow_agent_usage: bool = True
    allow_embedding: bool = True
    retention_days: int = Field(ge=1, default=365)


class DataHandlingPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID | None = None
    classification: str
    allowed_models: list[str]
    allowed_providers: list[str]
    allow_external_processing: bool
    allow_export: bool
    allow_agent_usage: bool
    allow_embedding: bool
    retention_days: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# PII Policies
# ---------------------------------------------------------------------------
class PIIHandlingPolicyUpsert(BaseModel):
    pii_category: PIICategory
    action: PIIHandlingAction = PIIHandlingAction.MASK
    mask_pattern: str = "[REDACTED_{category}]"
    block_export: bool = False
    audit_on_detection: bool = True


class PIIHandlingPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID | None = None
    pii_category: str
    action: str
    mask_pattern: str
    block_export: bool
    audit_on_detection: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Retention & Legal Holds
# ---------------------------------------------------------------------------
class RetentionPolicyUpsert(BaseModel):
    resource_type: RetentionResourceType
    retention_days: int = Field(ge=1, default=90)
    legal_hold_exempt: bool = False
    delete_after: bool = False
    enabled: bool = True


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID | None = None
    resource_type: str
    retention_days: int
    legal_hold_exempt: bool
    delete_after: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


class LegalHoldCreate(BaseModel):
    name: str = Field(..., max_length=160)
    reason: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    resources: list[str] = Field(default_factory=list)


class LegalHoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    name: str
    reason: str
    created_by: str
    active: bool
    starts_at: datetime
    ends_at: datetime | None = None
    resources: list[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Access Reviews
# ---------------------------------------------------------------------------
class AccessReviewCreate(BaseModel):
    title: str = Field(..., max_length=160)


class AccessReviewItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    organization_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    role: str
    permissions: list[str]
    last_activity_at: datetime | None = None
    granted_at: datetime
    review_status: AccessReviewStatus
    recommendation: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None


class AccessReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    title: str
    initiated_by: str
    status: AccessReviewStatus
    total_users_reviewed: int
    flagged_inactive_count: int
    created_at: datetime
    completed_at: datetime | None = None
    items: list[AccessReviewItemResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Security Findings & Risk Acceptance
# ---------------------------------------------------------------------------
class SecurityFindingCreate(BaseModel):
    control_id: str | None = None
    severity: FindingSeverity = FindingSeverity.MEDIUM
    title: str = Field(..., max_length=255)
    description: str
    source: str = "AUTOMATED_SCANNER"
    owner: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RiskAcceptanceCreate(BaseModel):
    reason: str
    expires_at: datetime
    privileged_approval_id: str | None = None


class RiskAcceptanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID | None = None
    finding_id: str
    accepted_by: str
    reason: str
    starts_at: datetime
    expires_at: datetime
    privileged_approval_id: str | None = None
    created_at: datetime
    is_expired: bool = False


class SecurityFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID | None = None
    control_id: str | None = None
    severity: FindingSeverity
    status: FindingStatus
    title: str
    description: str
    source: str
    first_detected_at: datetime
    last_detected_at: datetime
    resolved_at: datetime | None = None
    owner: str | None = None
    details: dict[str, Any]
    age_days: int = 0
    risk_acceptances: list[RiskAcceptanceResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Privacy Requests
# ---------------------------------------------------------------------------
class PrivacyRequestCreate(BaseModel):
    user_id: uuid.UUID
    request_type: PrivacyRequestType
    resources: list[str] = Field(default_factory=list)
    notes: str | None = None


class PrivacyRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    user_id: uuid.UUID
    request_type: PrivacyRequestType
    status: PrivacyRequestStatus
    requested_by: str
    resources: list[str]
    governance_approval_id: str | None = None
    executed_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Posture, Readiness & Overview
# ---------------------------------------------------------------------------
class PillarPosture(BaseModel):
    name: str
    status: AssessmentStatus
    score: float
    controls_passed: int
    controls_total: int
    critical_findings: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


class SecurityPostureResponse(BaseModel):
    organization_id: uuid.UUID | None = None
    overall_score: float
    evaluated_at: datetime
    pillars: dict[str, PillarPosture]


class ComplianceReadinessResponse(BaseModel):
    organization_id: uuid.UUID | None = None
    decision: ReadinessDecision
    composite_score: float
    framework_scores: dict[str, float]
    passed_controls: int
    warning_controls: int
    failed_controls: int
    not_assessed_controls: int
    blockers: list[str]
    warnings: list[str]
    evaluated_at: datetime


class ComplianceOverviewResponse(BaseModel):
    organization_id: uuid.UUID | None = None
    security_posture: SecurityPostureResponse
    compliance_readiness: ComplianceReadinessResponse
    open_findings_count: int
    critical_findings_count: int
    active_legal_holds_count: int
    pending_privacy_requests_count: int
    pending_access_reviews_count: int
    last_assessment_time: datetime | None = None
