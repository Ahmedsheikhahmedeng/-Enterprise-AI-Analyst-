"""Unit tests for PII pattern detection, masking, and policy enforcement."""

import pytest

from app.compliance.enums import PIICategory, PIIHandlingAction
from app.compliance.exceptions import PolicyViolationError
from app.compliance.privacy import PIIGovernanceEngine


def test_pii_detection_coverage_across_types() -> None:
    sample_text = (
        "Contact alice@example.com or call 555-123-4567. "
        "Server IP 192.168.1.10. "
        "Payment card 4111-2222-3333-4444. "
        "SSN: 123-45-6789. "
        "Passport: A1234567. "
        "IBAN: GB29XAPI12345678901234. "
        "Dr. John Doe visited 123 Main Street."
    )
    results = PIIGovernanceEngine.scan_text(sample_text)
    detected_categories = {r.category for r in results}

    assert PIICategory.EMAIL in detected_categories
    assert PIICategory.PHONE in detected_categories
    assert PIICategory.IP in detected_categories
    assert PIICategory.CREDIT_CARD in detected_categories
    assert PIICategory.NATIONAL_ID in detected_categories
    assert PIICategory.PASSPORT in detected_categories
    assert PIICategory.BANK_ACCOUNT in detected_categories
    assert PIICategory.PERSON_NAME in detected_categories
    assert PIICategory.ADDRESS in detected_categories


def test_pii_masking_transformation() -> None:
    text = "Please reach out to support@enterprise.com regarding issue."
    masked_text, detected = PIIGovernanceEngine.apply_pii_policy(text)
    assert "[REDACTED_EMAIL]" in masked_text
    assert "support@enterprise.com" not in masked_text
    assert PIICategory.EMAIL in detected


def test_pii_blocking_action_raises_policy_error() -> None:
    text = "Confidential credit card: 4111-2222-3333-4444"
    policies = {PIICategory.CREDIT_CARD.value: PIIHandlingAction.BLOCK.value}

    with pytest.raises(PolicyViolationError) as exc_info:
        PIIGovernanceEngine.apply_pii_policy(text, policies=policies)

    assert "Operation blocked" in str(exc_info.value)
    assert "CREDIT_CARD" in str(exc_info.value)
