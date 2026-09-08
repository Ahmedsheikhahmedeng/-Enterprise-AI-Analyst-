"""Unit tests for restricted and sensitive data export governance."""

from app.compliance.classification import DataClassificationEngine
from app.compliance.enums import DataClassificationLevel


def test_public_and_internal_export_allowed() -> None:
    pub_verdict = DataClassificationEngine.evaluate_export_governance(
        DataClassificationLevel.PUBLIC.value, export_format="csv"
    )
    assert pub_verdict.allowed is True
    assert pub_verdict.verdict == "ALLOW"

    int_verdict = DataClassificationEngine.evaluate_export_governance(
        DataClassificationLevel.INTERNAL.value, export_format="json"
    )
    assert int_verdict.allowed is True
    assert int_verdict.verdict == "ALLOW"


def test_restricted_export_blocked_by_default() -> None:
    verdict = DataClassificationEngine.evaluate_export_governance(
        DataClassificationLevel.RESTRICTED.value, export_format="csv"
    )
    assert verdict.allowed is False
    assert verdict.verdict == "BLOCK"
    assert "prohibited" in verdict.reason.lower()


def test_sensitive_export_blocked() -> None:
    verdict = DataClassificationEngine.evaluate_export_governance(
        DataClassificationLevel.SENSITIVE.value, export_format="parquet"
    )
    assert verdict.allowed is False
    assert verdict.verdict == "BLOCK"
