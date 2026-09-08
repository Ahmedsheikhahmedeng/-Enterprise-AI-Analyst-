"""SBOM (Software Bill of Materials) evidence management."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class SBOMRecord:
    """Canonical SBOM release artifact metadata."""

    sbom_hash: str
    release_tag: str
    commit_sha: str
    package_count: int
    captured_at: str
    metadata_payload: dict[str, Any]


class SBOMManager:
    """Validates and digests Software Bill of Materials metadata."""

    @classmethod
    def generate_sbom_evidence_record(
        cls,
        release_tag: str,
        commit_sha: str,
        packages: list[dict[str, str]],
    ) -> SBOMRecord:
        """Create deterministic digest and evidence representation of an SBOM."""
        serialized = json.dumps(packages, sort_keys=True)
        sbom_digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        now = datetime.now(UTC).isoformat()

        return SBOMRecord(
            sbom_hash=sbom_digest,
            release_tag=release_tag,
            commit_sha=commit_sha,
            package_count=len(packages),
            captured_at=now,
            metadata_payload={
                "packages_sample": packages[:10],
                "generated_at": now,
                "tool": "syft_cyclonedx",
            },
        )
