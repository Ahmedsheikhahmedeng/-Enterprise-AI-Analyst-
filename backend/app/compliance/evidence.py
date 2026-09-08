"""Evidence store, SHA-256 hashing, immutable versioning, and freshness evaluation."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.compliance.enums import EvidenceFreshness, EvidenceType


class EvidenceEngine:
    """Handles cryptographic digest generation, versioning, and freshness checks for compliance evidence."""

    DEFAULT_STALENESS_DAYS: dict[str, int] = {
        EvidenceType.CONFIGURATION.value: 90,
        EvidenceType.SECURITY_TEST.value: 14,
        EvidenceType.AUTOMATED_TEST.value: 7,
        EvidenceType.AUDIT_EVENT.value: 30,
        EvidenceType.SRE_METRIC.value: 1,
        EvidenceType.RELIABILITY_RUN.value: 7,
        EvidenceType.ACCESS_REVIEW.value: 90,
        EvidenceType.POLICY.value: 180,
        EvidenceType.BACKUP_VERIFICATION.value: 7,
        EvidenceType.DEPLOYMENT_RECORD.value: 30,
    }

    @classmethod
    def compute_evidence_hash(
        cls,
        control_id: str,
        evidence_type: str,
        source: str,
        reference: str,
        metadata_payload: dict[str, Any],
        captured_at: datetime,
    ) -> str:
        """Compute deterministic SHA-256 digest of canonical evidence payload."""
        canonical_dict = {
            "control_id": control_id,
            "evidence_type": evidence_type,
            "source": source,
            "reference": reference,
            "captured_at": captured_at.isoformat(),
            "metadata": metadata_payload,
        }
        serialized = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def evaluate_freshness(
        cls,
        captured_at: datetime,
        evidence_type: str,
        expires_at: datetime | None = None,
        reference_time: datetime | None = None,
    ) -> EvidenceFreshness:
        """Determine temporal freshness of captured evidence."""
        now = reference_time or datetime.now(UTC)

        # 1. Check explicit expiration
        if expires_at and now > expires_at:
            return EvidenceFreshness.EXPIRED

        # 2. Check age against staleness policy
        max_days = cls.DEFAULT_STALENESS_DAYS.get(evidence_type, 30)
        age = now - captured_at
        if age > timedelta(days=max_days):
            return EvidenceFreshness.STALE

        return EvidenceFreshness.FRESH
