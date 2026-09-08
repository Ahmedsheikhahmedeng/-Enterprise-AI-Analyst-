"""Deterministic baseline catalog of Enterprise Security & Compliance Controls."""

from dataclasses import dataclass, field
from typing import Any

from app.compliance.enums import (
    ComplianceFramework,
    ControlCategory,
    ControlSeverity,
)


@dataclass(frozen=True)
class BaselineControlDefinition:
    """Canonical definition of an enterprise security or compliance control."""

    id: str
    framework: ComplianceFramework
    control_code: str
    name: str
    description: str
    category: ControlCategory
    severity: ControlSeverity
    automated: bool = True
    required_evidence_types: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)


# Catalog of 23 canonical baseline controls
CANONICAL_CONTROLS: list[BaselineControlDefinition] = [
    # 1. Identity & Authentication
    BaselineControlDefinition(
        id="ctrl-auth-001",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-AUTH-001",
        name="Cryptographic Password Hashing & Salting",
        description="Enforces secure password hashing algorithms (Argon2id/Bcrypt) with high cost factors and salt.",
        category=ControlCategory.AUTHENTICATION,
        severity=ControlSeverity.CRITICAL,
        required_evidence_types=["SECURITY_TEST", "CONFIGURATION"],
    ),
    BaselineControlDefinition(
        id="ctrl-auth-002",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-AUTH-002",
        name="Token Lifecycle, Expiration & Refresh Rotation",
        description="JWT access tokens expire within 15 minutes; refresh tokens use single-use rotation and revocation tracking.",
        category=ControlCategory.AUTHENTICATION,
        severity=ControlSeverity.CRITICAL,
        required_evidence_types=["SECURITY_TEST", "AUDIT_EVENT"],
    ),
    # 2. Authorization & RBAC
    BaselineControlDefinition(
        id="ctrl-rbac-001",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-RBAC-001",
        name="Granular Role-Based Access Control",
        description="All API endpoints and platform operations strictly enforce explicit role-to-permission mappings.",
        category=ControlCategory.AUTHORIZATION,
        severity=ControlSeverity.CRITICAL,
        required_evidence_types=["AUTOMATED_TEST", "POLICY"],
    ),
    BaselineControlDefinition(
        id="ctrl-rbac-002",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-RBAC-002",
        name="Tenant Context Scoping on Operations",
        description="Ensures every authorized session executes strictly within an authenticated tenant organization boundary.",
        category=ControlCategory.AUTHORIZATION,
        severity=ControlSeverity.CRITICAL,
        required_evidence_types=["SECURITY_TEST", "AUDIT_EVENT"],
    ),
    # 3. Tenant Isolation
    BaselineControlDefinition(
        id="ctrl-tenant-001",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-TENANT-001",
        name="Cross-Tenant Read Query Suppression",
        description="Queries, vector search, and caches filter data exclusively by requesting tenant organization_id.",
        category=ControlCategory.ACCESS_CONTROL,
        severity=ControlSeverity.CRITICAL,
        required_evidence_types=["SECURITY_TEST", "RELIABILITY_RUN"],
    ),
    BaselineControlDefinition(
        id="ctrl-tenant-002",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-TENANT-002",
        name="Cross-Tenant Mutation Boundary Enforcement",
        description="Updates, deletes, and insertions reject any payload or foreign key targeting foreign tenant resources.",
        category=ControlCategory.ACCESS_CONTROL,
        severity=ControlSeverity.CRITICAL,
        required_evidence_types=["SECURITY_TEST", "AUTOMATED_TEST"],
    ),
    # 4. Secrets Management
    BaselineControlDefinition(
        id="ctrl-secret-001",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-SECRET-001",
        name="Secret Redaction in Logs and Traces",
        description="Tokens, passwords, and API keys are automatically redacted from application logs, metrics, and error traces.",
        category=ControlCategory.DATA_PROTECTION,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["SECURITY_TEST", "CONFIGURATION"],
    ),
    BaselineControlDefinition(
        id="ctrl-secret-002",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-SECRET-002",
        name="Zero Default or Insecure Hardcoded Secrets",
        description="Production configurations prohibit default symmetric keys, fallback credentials, and insecure secrets.",
        category=ControlCategory.DATA_PROTECTION,
        severity=ControlSeverity.CRITICAL,
        required_evidence_types=["SECURITY_TEST", "CONFIGURATION"],
    ),
    # 5. Network Security
    BaselineControlDefinition(
        id="ctrl-net-001",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-NET-001",
        name="Server-Side Request Forgery (SSRF) Defense",
        description="Outbound network calls validate URLs and block loopback, link-local, private IP ranges, and AWS metadata endpoints.",
        category=ControlCategory.NETWORK_SECURITY,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["SECURITY_TEST", "CONFIGURATION"],
    ),
    BaselineControlDefinition(
        id="ctrl-net-002",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-NET-002",
        name="Restricted Outbound Network Egress",
        description="External egress is restricted to approved LLM providers, storage endpoints, and data source connectors.",
        category=ControlCategory.NETWORK_SECURITY,
        severity=ControlSeverity.MEDIUM,
        required_evidence_types=["CONFIGURATION", "POLICY"],
    ),
    # 6. Data Security
    BaselineControlDefinition(
        id="ctrl-data-001",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-DATA-001",
        name="File Upload Content & Extension Validation",
        description="Ingested files must match allowed MIME types, magic byte signatures, and size budgets before processing.",
        category=ControlCategory.DATA_PROTECTION,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["SECURITY_TEST", "AUTOMATED_TEST"],
    ),
    BaselineControlDefinition(
        id="ctrl-data-002",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-DATA-002",
        name="CSV Formula Injection & Object Key Safety",
        description="Spreadsheets and exported tables escape formula prefixes (=, +, -, @); object keys sanitize traversal characters.",
        category=ControlCategory.DATA_PROTECTION,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["SECURITY_TEST", "AUTOMATED_TEST"],
    ),
    # 7. Logging & Auditing
    BaselineControlDefinition(
        id="ctrl-log-001",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-LOG-001",
        name="Immutable Audit Event Logging",
        description="All security, auth, and data mutation events generate persistent, structured audit records.",
        category=ControlCategory.LOGGING,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["AUDIT_EVENT", "AUTOMATED_TEST"],
    ),
    BaselineControlDefinition(
        id="ctrl-log-002",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-LOG-002",
        name="Audit Chain Cryptographic Integrity",
        description="Audit events form sequential cryptographic hash chains enabling detection of unauthorized tampering.",
        category=ControlCategory.LOGGING,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["SECURITY_TEST", "AUDIT_EVENT"],
    ),
    # 8. AI Governance & Security
    BaselineControlDefinition(
        id="ctrl-ai-001",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-AI-001",
        name="Prompt Injection Defense & Classification",
        description="User inputs and document payloads undergo heuristic and semantic scanning for prompt injection attacks.",
        category=ControlCategory.AI_GOVERNANCE,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["SECURITY_TEST", "AUTOMATED_TEST"],
    ),
    BaselineControlDefinition(
        id="ctrl-ai-002",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-AI-002",
        name="Untrusted Document Handling Boundary",
        description="Unstructured documents are parsed within sanitized environments with strict extraction limits.",
        category=ControlCategory.AI_GOVERNANCE,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["AUTOMATED_TEST", "POLICY"],
    ),
    BaselineControlDefinition(
        id="ctrl-ai-003",
        framework=ComplianceFramework.INTERNAL_SECURITY_BASELINE,
        control_code="SEC-AI-003",
        name="Output Grounding & Hallucination Control",
        description="LLM responses must provide source citations and pass factual grounding checks before publication.",
        category=ControlCategory.AI_GOVERNANCE,
        severity=ControlSeverity.MEDIUM,
        required_evidence_types=["AUTOMATED_TEST", "CONFIGURATION"],
    ),
    # 9. SOC 2 Readiness Mappings
    BaselineControlDefinition(
        id="ctrl-soc2-cc61",
        framework=ComplianceFramework.SOC2_READINESS,
        control_code="SOC2-CC6.1",
        name="Logical Access Controls and Boundary Protection",
        description="Access to data and systems is restricted to authorized users via RBAC and tenant boundaries.",
        category=ControlCategory.ACCESS_CONTROL,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["SECURITY_TEST", "POLICY", "ACCESS_REVIEW"],
    ),
    BaselineControlDefinition(
        id="ctrl-soc2-cc62",
        framework=ComplianceFramework.SOC2_READINESS,
        control_code="SOC2-CC6.2",
        name="User Authentication and Credential Management",
        description="Authentication systems verify credentials using strong hashing and secure session tokens.",
        category=ControlCategory.AUTHENTICATION,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["SECURITY_TEST", "CONFIGURATION"],
    ),
    BaselineControlDefinition(
        id="ctrl-soc2-cc63",
        framework=ComplianceFramework.SOC2_READINESS,
        control_code="SOC2-CC6.3",
        name="Privilege Management & Periodic Access Review",
        description="Administrative and privileged roles undergo periodic access reviews; stale permissions are flagged.",
        category=ControlCategory.ACCESS_CONTROL,
        severity=ControlSeverity.MEDIUM,
        required_evidence_types=["ACCESS_REVIEW", "AUDIT_EVENT"],
    ),
    # 10. ISO 27001 Readiness Mappings
    BaselineControlDefinition(
        id="ctrl-iso-a91",
        framework=ComplianceFramework.ISO27001_READINESS,
        control_code="ISO-A.9.1",
        name="Access Control Policy and Business Requirements",
        description="Formal access policies restrict access to information assets according to classification.",
        category=ControlCategory.ACCESS_CONTROL,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["POLICY", "AUTOMATED_TEST"],
    ),
    BaselineControlDefinition(
        id="ctrl-iso-a121",
        framework=ComplianceFramework.ISO27001_READINESS,
        control_code="ISO-A.12.1",
        name="Operational Procedures & System Health Validation",
        description="System operations, incident response, and reliability validation are documented and automated.",
        category=ControlCategory.MONITORING,
        severity=ControlSeverity.MEDIUM,
        required_evidence_types=["SRE_METRIC", "RELIABILITY_RUN"],
    ),
    # 11. Privacy Baseline
    BaselineControlDefinition(
        id="ctrl-priv-001",
        framework=ComplianceFramework.PRIVACY_BASELINE,
        control_code="PRIV-001",
        name="Right to Erasure & Privacy Request Workflow",
        description="Structured, governed workflow for processing data deletion requests under audit supervision.",
        category=ControlCategory.PRIVACY,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["AUDIT_EVENT", "POLICY"],
    ),
    BaselineControlDefinition(
        id="ctrl-priv-002",
        framework=ComplianceFramework.PRIVACY_BASELINE,
        control_code="PRIV-002",
        name="Data Retention Enforcement & Legal Hold Governance",
        description="Configurable retention schedules mark expired data for deletion; active legal holds freeze eligibility.",
        category=ControlCategory.PRIVACY,
        severity=ControlSeverity.HIGH,
        required_evidence_types=["POLICY", "CONFIGURATION"],
    ),
]


class ControlCatalogRegistry:
    """In-memory catalog provider for baseline enterprise controls."""

    def __init__(self) -> None:
        self._controls: dict[str, BaselineControlDefinition] = {c.id: c for c in CANONICAL_CONTROLS}

    def get(self, control_id: str) -> BaselineControlDefinition | None:
        return self._controls.get(control_id)

    def list_all(self) -> list[BaselineControlDefinition]:
        return list(self._controls.values())

    def list_by_framework(self, framework: ComplianceFramework) -> list[BaselineControlDefinition]:
        return [c for c in self._controls.values() if c.framework == framework]


GLOBAL_CONTROL_CATALOG = ControlCatalogRegistry()
