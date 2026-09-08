"""Enums and types for Enterprise Security & Compliance Governance."""

from enum import StrEnum


class ComplianceFramework(StrEnum):
    """Supported compliance and security baseline frameworks."""

    INTERNAL_SECURITY_BASELINE = "INTERNAL_SECURITY_BASELINE"
    SOC2_READINESS = "SOC2_READINESS"
    ISO27001_READINESS = "ISO27001_READINESS"
    PRIVACY_BASELINE = "PRIVACY_BASELINE"


class ControlCategory(StrEnum):
    """Categorization of enterprise security and compliance controls."""

    ACCESS_CONTROL = "ACCESS_CONTROL"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    DATA_PROTECTION = "DATA_PROTECTION"
    NETWORK_SECURITY = "NETWORK_SECURITY"
    LOGGING = "LOGGING"
    MONITORING = "MONITORING"
    INCIDENT_RESPONSE = "INCIDENT_RESPONSE"
    CHANGE_MANAGEMENT = "CHANGE_MANAGEMENT"
    BACKUP = "BACKUP"
    PRIVACY = "PRIVACY"
    VENDOR_RISK = "VENDOR_RISK"
    AI_GOVERNANCE = "AI_GOVERNANCE"


class ControlSeverity(StrEnum):
    """Severity tier indicating impact of control failure."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AssessmentStatus(StrEnum):
    """Outcome status of a compliance control assessment."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_ASSESSED = "NOT_ASSESSED"


class EvidenceType(StrEnum):
    """Classification of verification evidence types."""

    CONFIGURATION = "CONFIGURATION"
    AUDIT_EVENT = "AUDIT_EVENT"
    SECURITY_TEST = "SECURITY_TEST"
    AUTOMATED_TEST = "AUTOMATED_TEST"
    SRE_METRIC = "SRE_METRIC"
    RELIABILITY_RUN = "RELIABILITY_RUN"
    ACCESS_REVIEW = "ACCESS_REVIEW"
    POLICY = "POLICY"
    BACKUP_VERIFICATION = "BACKUP_VERIFICATION"
    DEPLOYMENT_RECORD = "DEPLOYMENT_RECORD"


class EvidenceFreshness(StrEnum):
    """Temporal validity classification of captured evidence."""

    FRESH = "FRESH"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    MISSING = "MISSING"


class DataClassificationLevel(StrEnum):
    """Data sensitivity classification hierarchy."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"
    SENSITIVE = "SENSITIVE"


class PIICategory(StrEnum):
    """Personally Identifiable Information classification categories."""

    EMAIL = "EMAIL"
    PHONE = "PHONE"
    IP = "IP"
    PERSON_NAME = "PERSON_NAME"
    NATIONAL_ID = "NATIONAL_ID"
    PASSPORT = "PASSPORT"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    CREDIT_CARD = "CREDIT_CARD"
    ADDRESS = "ADDRESS"


class PIIHandlingAction(StrEnum):
    """Operational actions applied to detected PII."""

    DETECT = "DETECT"
    MASK = "MASK"
    BLOCK = "BLOCK"
    AUDIT = "AUDIT"
    ALLOW = "ALLOW"


class RetentionResourceType(StrEnum):
    """Resource domains governed by data retention policies."""

    DOCUMENTS = "DOCUMENTS"
    DATASETS = "DATASETS"
    MEMORY = "MEMORY"
    AUDIT_EVENTS = "AUDIT_EVENTS"
    SECURITY_EVENTS = "SECURITY_EVENTS"
    INCIDENTS = "INCIDENTS"
    REPORTS = "REPORTS"
    EVIDENCE = "EVIDENCE"


class PrivacyRequestType(StrEnum):
    """Types of data subject privacy requests."""

    RIGHT_TO_DELETE = "RIGHT_TO_DELETE"
    DATA_ACCESS = "DATA_ACCESS"
    DATA_PORTABILITY = "DATA_PORTABILITY"
    RECTIFICATION = "RECTIFICATION"


class PrivacyRequestStatus(StrEnum):
    """Lifecycle state machine for privacy requests."""

    REQUESTED = "REQUESTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class AccessReviewStatus(StrEnum):
    """State of an access review evaluation item."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REVOKE_RECOMMENDED = "REVOKE_RECOMMENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class FindingSeverity(StrEnum):
    """Severity tier for identified security vulnerabilities."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingStatus(StrEnum):
    """Lifecycle states for a security finding."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"
    ACCEPTED_RISK = "ACCEPTED_RISK"


class ReadinessDecision(StrEnum):
    """Overall release decision for enterprise compliance readiness."""

    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"


class AuditIntegrityStatus(StrEnum):
    """Cryptographic audit chain verification result."""

    VALID = "VALID"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"
