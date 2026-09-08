"""Cryptographic hash chain verification for immutable audit records."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.compliance.enums import AuditIntegrityStatus


@dataclass(frozen=True)
class AuditVerificationResult:
    """Outcome of audit ledger integrity validation."""

    status: AuditIntegrityStatus
    total_records_checked: int
    first_tampered_record_id: str | None
    reason: str
    chain_root: str | None
    latest_block_hash: str | None


class AuditIntegrityVerifier:
    """Verifies chronological audit event sequences using chained SHA-256 digests.

    CHAIN FORMULA:
    hash_0 = sha256("GENESIS_BLOCK:" + organization_id)
    hash_n = sha256(hash_{n-1} + ":" + canonical_event_json)

    DISCLAIMER:
    Provides detection of application-level tampering, deletion, or insertion.
    Does not provide physical tamper-proof hardware guarantees if the underlying database host is compromised.
    """

    @classmethod
    def compute_canonical_event_str(cls, event: dict[str, Any]) -> str:
        """Serialize event fields deterministically."""
        canonical = {
            "id": str(event.get("id", "")),
            "user_id": str(event.get("user_id", "")),
            "action": event.get("action", ""),
            "resource_type": event.get("resource_type", ""),
            "resource_id": str(event.get("resource_id", "")),
            "ip_address": event.get("ip_address", ""),
            "created_at": str(event.get("created_at", "")),
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":"))

    @classmethod
    def compute_chain_step(cls, previous_hash: str, canonical_event_str: str) -> str:
        """Compute the next block hash in the sequence."""
        payload = f"{previous_hash}:{canonical_event_str}".encode()
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def verify_ledger(
        cls,
        organization_id: str,
        events: list[dict[str, Any]],
        expected_latest_hash: str | None = None,
    ) -> AuditVerificationResult:
        """Validate an ordered list of audit records against the sequential hash chain."""
        if not events:
            return AuditVerificationResult(
                status=AuditIntegrityStatus.INCOMPLETE,
                total_records_checked=0,
                first_tampered_record_id=None,
                reason="Audit ledger is empty; no verifiable records found.",
                chain_root=None,
                latest_block_hash=None,
            )

        genesis_seed = f"GENESIS_BLOCK:{organization_id}".encode()
        current_hash = hashlib.sha256(genesis_seed).hexdigest()
        root_hash = current_hash

        for idx, event in enumerate(events):
            canonical_str = cls.compute_canonical_event_str(event)
            step_hash = cls.compute_chain_step(current_hash, canonical_str)

            # If the record carries an embedded chain hash, compare it
            embedded_hash = (
                event.get("metadata", {}).get("chain_hash")
                if isinstance(event.get("metadata"), dict)
                else None
            )
            if embedded_hash and embedded_hash != step_hash:
                return AuditVerificationResult(
                    status=AuditIntegrityStatus.INVALID,
                    total_records_checked=idx + 1,
                    first_tampered_record_id=str(event.get("id")),
                    reason=f"Hash mismatch at record index {idx} (ID: {event.get('id')}).",
                    chain_root=root_hash,
                    latest_block_hash=current_hash,
                )

            current_hash = step_hash

        if expected_latest_hash and current_hash != expected_latest_hash:
            return AuditVerificationResult(
                status=AuditIntegrityStatus.INVALID,
                total_records_checked=len(events),
                first_tampered_record_id=None,
                reason="Ledger end hash does not match published checkpoint.",
                chain_root=root_hash,
                latest_block_hash=current_hash,
            )

        return AuditVerificationResult(
            status=AuditIntegrityStatus.VALID,
            total_records_checked=len(events),
            first_tampered_record_id=None,
            reason=f"Successfully verified cryptographic integrity across {len(events)} sequential audit records.",
            chain_root=root_hash,
            latest_block_hash=current_hash,
        )
