"""Unit tests for compliance control catalog and baseline definitions."""

from app.compliance.control_catalog import CANONICAL_CONTROLS, GLOBAL_CONTROL_CATALOG
from app.compliance.enums import ComplianceFramework, ControlCategory, ControlSeverity


def test_control_catalog_total_and_codes() -> None:
    all_controls = GLOBAL_CONTROL_CATALOG.list_all()
    assert len(all_controls) == 24
    assert len(CANONICAL_CONTROLS) == 24

    codes = {c.control_code for c in all_controls}
    # Identity
    assert "SEC-AUTH-001" in codes
    assert "SEC-AUTH-002" in codes
    # Authorization
    assert "SEC-RBAC-001" in codes
    assert "SEC-RBAC-002" in codes
    # Tenant Isolation
    assert "SEC-TENANT-001" in codes
    assert "SEC-TENANT-002" in codes
    # Secrets
    assert "SEC-SECRET-001" in codes
    assert "SEC-SECRET-002" in codes
    # Network
    assert "SEC-NET-001" in codes
    assert "SEC-NET-002" in codes
    # Data
    assert "SEC-DATA-001" in codes
    assert "SEC-DATA-002" in codes
    # Logging
    assert "SEC-LOG-001" in codes
    assert "SEC-LOG-002" in codes
    # AI Security
    assert "SEC-AI-001" in codes
    assert "SEC-AI-002" in codes
    assert "SEC-AI-003" in codes
    # SOC2
    assert "SOC2-CC6.1" in codes
    assert "SOC2-CC6.2" in codes
    assert "SOC2-CC6.3" in codes
    # ISO27001
    assert "ISO-A.9.1" in codes
    assert "ISO-A.12.1" in codes
    # Privacy
    assert "PRIV-001" in codes
    assert "PRIV-002" in codes


def test_framework_query_filtering() -> None:
    soc2 = GLOBAL_CONTROL_CATALOG.list_by_framework(ComplianceFramework.SOC2_READINESS)
    assert len(soc2) == 3
    assert all(c.framework == ComplianceFramework.SOC2_READINESS for c in soc2)

    iso = GLOBAL_CONTROL_CATALOG.list_by_framework(ComplianceFramework.ISO27001_READINESS)
    assert len(iso) == 2

    privacy = GLOBAL_CONTROL_CATALOG.list_by_framework(ComplianceFramework.PRIVACY_BASELINE)
    assert len(privacy) == 2


def test_control_attributes_completeness() -> None:
    for ctrl in GLOBAL_CONTROL_CATALOG.list_all():
        assert ctrl.id.startswith("ctrl-")
        assert len(ctrl.name) > 5
        assert len(ctrl.description) > 10
        assert isinstance(ctrl.category, ControlCategory)
        assert isinstance(ctrl.severity, ControlSeverity)
        assert isinstance(ctrl.required_evidence_types, list)
