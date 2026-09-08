"""Input validators and safety guardrails for cross-encoder reranking."""

import logging
import unicodedata
from uuid import UUID

from app.reranking.config import RerankerConfig
from app.reranking.exceptions import RerankerInputError, RerankerTenantError
from app.retrieval.hybrid.models import FusedCandidate

logger = logging.getLogger(__name__)


class RerankerValidator:
    """Validates inputs, boundaries, and security constraints for reranking."""

    @staticmethod
    def validate_query(query: str) -> str:
        """Normalize and validate query string."""
        cleaned = unicodedata.normalize("NFC", query).strip()
        if not cleaned:
            raise RerankerInputError("Query cannot be empty or whitespace for reranking.")
        return cleaned

    @staticmethod
    def validate_tenant_boundary(
        candidates: list[FusedCandidate],
        organization_id: UUID,
    ) -> None:
        """Enforce strict multi-tenant isolation across all candidates.

        Raises:
            RerankerTenantError: If any candidate belongs to another organization.
        """
        for cand in candidates:
            org_id = cand.organization_id
            if org_id != organization_id:
                logger.error(
                    "Security violation: candidate chunk %s belongs to org %s, expected %s",
                    cand.chunk_id,
                    org_id,
                    organization_id,
                )
                raise RerankerTenantError(
                    f"Candidate chunk '{cand.chunk_id}' violates organization boundary.",
                    details={
                        "chunk_id": str(cand.chunk_id),
                        "candidate_org_id": str(org_id),
                        "expected_org_id": str(organization_id),
                    },
                )

    @staticmethod
    def truncate_text_if_needed(
        text: str,
        max_tokens: int,
        approx_chars_per_token: int = 4,
    ) -> str:
        """Apply deterministic length bounding to prevent cross-encoder tensor explosion."""
        max_chars = max_tokens * approx_chars_per_token
        if len(text) <= max_chars:
            return text

        logger.debug(
            "Candidate text length (%d chars) exceeds limit (%d chars); truncating tail.",
            len(text),
            max_chars,
        )
        return text[:max_chars].rsplit(" ", 1)[0] + "..."

    @staticmethod
    def bound_candidates(
        candidates: list[FusedCandidate],
        config: RerankerConfig,
        requested_limit: int | None = None,
    ) -> list[FusedCandidate]:
        """Limit candidate pool size according to safety ceiling and requested parameters."""
        ceiling = config.max_candidates
        effective_k = ceiling
        if requested_limit is not None and requested_limit > 0:
            effective_k = min(requested_limit, ceiling)
        return candidates[:effective_k]
