"""Verification services: citation validation, claim extraction, and hallucination gating."""

import logging
import re
import uuid

from app.response_orchestration.domain.enums import ClaimStatus
from app.response_orchestration.domain.models import (
    Claim,
    EvidenceBundle,
)

logger = logging.getLogger(__name__)


class VerificationService:
    """Validates citations against available evidence, extracts claims, and filters hallucinations."""

    # Matches citation markers like [D1], [S2], [G1], [M3]
    _CITATION_REGEX = re.compile(r"\[([DSGM]\d+)\]")

    def validate_and_repair_citations(
        self,
        answer_text: str,
        evidence_bundle: EvidenceBundle,
    ) -> tuple[str, list[str]]:
        """Verify cited tokens exist in evidence bundle.

        Strips phantom citation tags that lack ground truth evidence.
        """
        valid_citations = {it.citation_id for it in evidence_bundle.items if it.citation_id}
        claimed = self._CITATION_REGEX.findall(answer_text)
        repaired_text = answer_text

        verified_citations: list[str] = []
        for tag in set(claimed):
            full_tag = f"[{tag}]"
            if full_tag in valid_citations:
                verified_citations.append(full_tag)
            else:
                # Phantom citation detected: strip from generated response text
                logger.warning("Stripping hallucinated phantom citation: %s", full_tag)
                repaired_text = repaired_text.replace(full_tag, "").strip()

        # Clean up double spaces caused by tag removal
        repaired_text = re.sub(r" +", " ", repaired_text)
        return repaired_text, sorted(verified_citations)

    def extract_and_verify_claims(
        self,
        answer_text: str,
        evidence_bundle: EvidenceBundle,
    ) -> tuple[list[Claim], float]:
        """Extract sentence-level statements, associate citations, and determine claim support."""
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?؟])\s+", answer_text)
            if s.strip() and len(s.strip()) > 8
        ]

        if not sentences:
            return [], 0.0

        claims: list[Claim] = []
        valid_citations = {it.citation_id: it for it in evidence_bundle.items if it.citation_id}

        for _idx, sentence in enumerate(sentences):
            tags = [f"[{t}]" for t in self._CITATION_REGEX.findall(sentence)]
            supporting_ids = []

            for tag in tags:
                ev = valid_citations.get(tag)
                if ev:
                    supporting_ids.append(ev.evidence_id)

            if supporting_ids:
                status = ClaimStatus.SUPPORTED
            elif not tags:
                # Factual claim made without any citation
                status = ClaimStatus.UNSUPPORTED
            else:
                status = ClaimStatus.UNSUPPORTED

            claim = Claim(
                claim_id=str(uuid.uuid4()),
                statement=sentence,
                required_evidence_type=None,
                citations_claimed=tags,
                status=status,
                supporting_evidence_ids=supporting_ids,
            )
            claims.append(claim)

        # Compute evidence coverage
        supported_count = sum(
            1
            for c in claims
            if c.status in (ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED)
        )
        coverage = supported_count / len(claims) if claims else 0.0
        return claims, round(coverage, 4)
