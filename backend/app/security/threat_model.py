"""Programmatic STRIDE Threat Model Metadata & Mapping — TASK 22.

Provides a structured representation of threats, assets, attack surfaces,
mitigations, and residual risks aligned with docs/security/threat_model.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class STRIDECategory(StrEnum):
    SPOOFING = "Spoofing"
    TAMPERING = "Tampering"
    REPUDIATION = "Repudiation"
    INFORMATION_DISCLOSURE = "Information Disclosure"
    DENIAL_OF_SERVICE = "Denial of Service"
    ELEVATION_OF_PRIVILEGE = "Elevation of Privilege"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ThreatRecord:
    threat_id: str
    category: STRIDECategory
    asset: str
    attack_surface: str
    attack_vector: str
    impact: str
    likelihood: str
    risk: RiskLevel
    mitigation: str
    test_reference: str
    residual_risk: str


# Baseline STRIDE threat inventory
SYSTEM_THREAT_MODEL: list[ThreatRecord] = [
    ThreatRecord(
        threat_id="THR-AUTH-01",
        category=STRIDECategory.SPOOFING,
        asset="JWT Authentication Tokens",
        attack_surface="HTTP API / JWT",
        attack_vector="Algorithm confusion (alg=none) or signature tampering",
        impact="Full account takeover and arbitrary caller impersonation",
        likelihood="Medium",
        risk=RiskLevel.CRITICAL,
        mitigation="Strict algorithm allowlist ['HS256'], rejection of alg=none, mandatory exp/iat/iss validation",
        test_reference="test_auth_security.py::test_jwt_alg_none_rejected",
        residual_risk="Compromise of application JWT secret key allows token forging (mitigated by key rotation).",
    ),
    ThreatRecord(
        threat_id="THR-AUTHZ-01",
        category=STRIDECategory.ELEVATION_OF_PRIVILEGE,
        asset="Multi-Tenant Domain Entities",
        attack_surface="HTTP API / IDOR",
        attack_vector="Direct manipulation of resource UUIDs (cross-tenant access)",
        impact="Unauthorized data exfiltration or state mutation across tenant boundaries",
        likelihood="High",
        risk=RiskLevel.CRITICAL,
        mitigation="Central TenantSecurityPolicy asserting tenant context against entity ownership on all routes",
        test_reference="test_tenant_isolation_security.py::test_cross_tenant_report_access_rejected",
        residual_risk="Developer omission on newly written custom queries without TenantScopedMixin.",
    ),
    ThreatRecord(
        threat_id="THR-LLM-01",
        category=STRIDECategory.TAMPERING,
        asset="AI Analyst Reasoning & Output",
        attack_surface="RAG / Document Ingestion / LLM",
        attack_vector="Indirect prompt injection embedded in uploaded PDFs/CSVs",
        impact="Unauthorized prompt disclosure, policy subversion, or corrupted analysis output",
        likelihood="High",
        risk=RiskLevel.HIGH,
        mitigation="PromptInjectionDetector classifying inputs into benign/suspicious/high_risk with system boundary isolation",
        test_reference="test_prompt_injection.py::test_direct_prompt_injection_patterns",
        residual_risk="Adversarial zero-day LLM jailbreaks cannot be mathematically eliminated.",
    ),
    ThreatRecord(
        threat_id="THR-SQL-01",
        category=STRIDECategory.TAMPERING,
        asset="Analytical Relational Database",
        attack_surface="SQL Agent / Text-to-SQL",
        attack_vector="SQL injection via prompt engineering or Cartesian join resource exhaustion",
        impact="Database state corruption, unauthorized table dumps, or server DoS",
        likelihood="Medium",
        risk=RiskLevel.CRITICAL,
        mitigation="SQLASTValidator enforcing SELECT-only, table allowlist, timeouts, and join limits",
        test_reference="test_sql_security.py::test_destructive_sql_mutation_rejected",
        residual_risk="Complex analytics queries may cause memory pressure within allowed SELECT parameters.",
    ),
    ThreatRecord(
        threat_id="THR-SSRF-01",
        category=STRIDECategory.INFORMATION_DISCLOSURE,
        asset="Internal VPC Infrastructure & Cloud Metadata",
        attack_surface="HTTP API / Future URL Fetchers",
        attack_vector="Targeting localhost, private RFC-1918 subnets, or 169.254.169.254",
        impact="Cloud instance credential theft or lateral movement within internal services",
        likelihood="Medium",
        risk=RiskLevel.CRITICAL,
        mitigation="SSRFProtection with IP resolution, private CIDR blocklist, and redirect checks",
        test_reference="test_ssrf.py::test_private_ip_blocked",
        residual_risk="DNS rebinding attacks if client-side pinning is bypassed by underlying OS resolver.",
    ),
    ThreatRecord(
        threat_id="THR-FILE-01",
        category=STRIDECategory.TAMPERING,
        asset="Host Storage & Ingestion Pipeline",
        attack_surface="File Upload / Ingestion",
        attack_vector="MIME spoofing, path traversal filenames (../../etc/passwd), or executable uploads",
        impact="Remote code execution or arbitrary file overwrites",
        likelihood="Medium",
        risk=RiskLevel.HIGH,
        mitigation="FileSecurityValidator with magic-byte verification, sanitized filenames, and strict extension allowlist",
        test_reference="test_file_security.py::test_path_traversal_filename_blocked",
        residual_risk="Malformed or deeply nested PDF parsing library vulnerabilities.",
    ),
    ThreatRecord(
        threat_id="THR-EXP-01",
        category=STRIDECategory.TAMPERING,
        asset="User Spreadsheet Applications",
        attack_surface="Reports / CSV Exports",
        attack_vector="Formula Injection / DDE commands (=cmd|'/c calc'!A1) in exported cells",
        impact="Client-side remote command execution when user opens exported CSV in Excel",
        likelihood="Medium",
        risk=RiskLevel.MEDIUM,
        mitigation="sanitize_csv_cell prefixing leading formula symbols (=, +, -, @, \\t, \\r) with an apostrophe",
        test_reference="test_exports_security.py::test_csv_formula_injection_prefixed",
        residual_risk="Third-party export parsers stripping leading apostrophes prior to cell evaluation.",
    ),
    ThreatRecord(
        threat_id="THR-DOS-01",
        category=STRIDECategory.DENIAL_OF_SERVICE,
        asset="Application Resources & LLM Provider Quotas",
        attack_surface="HTTP API Endpoints",
        attack_vector="High-frequency request flooding on expensive AI and export endpoints",
        impact="Service degradation, increased operational costs, and worker exhaustion",
        likelihood="High",
        risk=RiskLevel.HIGH,
        mitigation="Sliding-window RateLimiter with per-endpoint thresholds and Retry-After headers",
        test_reference="test_rate_limiting.py::test_rate_limit_exceeded_returns_429",
        residual_risk="Distributed botnets spreading requests across thousands of distinct residential IPs.",
    ),
]


def get_threat_model_summary() -> dict[str, int]:
    """Return count of identified threats grouped by category."""
    summary: dict[str, int] = {}
    for threat in SYSTEM_THREAT_MODEL:
        summary[threat.category] = summary.get(threat.category, 0) + 1
    return summary
