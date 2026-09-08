"""PII governance engine, privacy event emissions, and Right-to-Delete workflow."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.compliance.enums import PIICategory, PIIHandlingAction
from app.compliance.exceptions import PolicyViolationError


@dataclass(frozen=True)
class PIIDetectionResult:
    """Detected PII match metadata without retaining sensitive plain text."""

    category: PIICategory
    count: int
    masked_sample: str


@dataclass(frozen=True)
class PrivacyAuditRecord:
    """Sanitized privacy event audit record."""

    event_type: str
    organization_id: str | None
    actor: str | None
    resource_type: str
    resource_id: str
    classification: str
    pii_types: list[str]
    timestamp: str


class PIIGovernanceEngine:
    """Deterministic PII pattern detector, masking transformer, and privacy event emitter.

    LIMITATIONS NOTICE:
    Regex-based pattern matching provides deterministic baseline detection for common high-confidence PII
    identifiers (emails, phones, IPs, credit cards, national IDs). Regex heuristics cannot guarantee 100%
    recall for unformatted person names, international addresses, or novel identification formats.
    """

    # High-confidence regex patterns
    PATTERNS: dict[PIICategory, re.Pattern[str]] = {
        PIICategory.EMAIL: re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        PIICategory.PHONE: re.compile(
            r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ),
        PIICategory.IP: re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        PIICategory.CREDIT_CARD: re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        PIICategory.NATIONAL_ID: re.compile(
            r"\b(?:\d{3}-\d{2}-\d{4}|\d{11})\b"
        ),  # SSN or 11-digit National ID
        PIICategory.PASSPORT: re.compile(r"\b[A-PR-WY]\d{7,8}\b"),
        PIICategory.BANK_ACCOUNT: re.compile(
            r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b"
        ),  # IBAN-like
        PIICategory.PERSON_NAME: re.compile(
            r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"
        ),
        PIICategory.ADDRESS: re.compile(
            r"\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)\b",
            re.IGNORECASE,
        ),
    }

    @classmethod
    def scan_text(cls, text: str) -> list[PIIDetectionResult]:
        """Detect all matching PII types in text payload."""
        results: list[PIIDetectionResult] = []
        for category, pattern in cls.PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                sample = f"***{matches[0][-3:]}" if len(matches[0]) >= 3 else "***"
                results.append(
                    PIIDetectionResult(category=category, count=len(matches), masked_sample=sample)
                )
        return results

    @classmethod
    def apply_pii_policy(
        cls,
        text: str,
        policies: dict[str, str] | None = None,  # category -> action
    ) -> tuple[str, list[PIICategory]]:
        """Apply configured actions (MASK, BLOCK, ALLOW) to text."""
        policies = policies or {}
        detected_categories: list[PIICategory] = []
        transformed_text = text

        for category, pattern in cls.PATTERNS.items():
            action = policies.get(category.value, PIIHandlingAction.MASK.value)
            matches = pattern.findall(transformed_text)
            if matches:
                detected_categories.append(category)
                if action == PIIHandlingAction.BLOCK.value:
                    raise PolicyViolationError(
                        f"Operation blocked: Content contains prohibited PII category '{category.value}'.",
                        policy_action=action,
                    )
                elif action == PIIHandlingAction.MASK.value:
                    transformed_text = pattern.sub(f"[REDACTED_{category.value}]", transformed_text)

        return transformed_text, detected_categories

    @classmethod
    def create_privacy_event(
        cls,
        event_type: str,
        organization_id: str | None,
        actor: str | None,
        resource_type: str,
        resource_id: str,
        classification: str,
        detected_pii: list[PIICategory],
    ) -> PrivacyAuditRecord:
        """Construct sanitized privacy audit record (zero sensitive values stored)."""
        return PrivacyAuditRecord(
            event_type=event_type,
            organization_id=organization_id,
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            classification=classification,
            pii_types=[p.value for p in detected_pii],
            timestamp=datetime.now(UTC).isoformat(),
        )
