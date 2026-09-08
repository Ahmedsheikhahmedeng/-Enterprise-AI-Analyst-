"""Groundedness evaluation verifying claim-to-evidence support."""

import re
from collections.abc import Sequence
from typing import Any

from app.evaluation.metrics.rag import extract_claims
from app.evaluation.models import GroundingMetrics


def evaluate_groundedness(
    answer: str,
    evidence_items: Sequence[dict[str, Any]],
) -> GroundingMetrics:
    """Assess whether factual statements in the answer are grounded by verified evidence."""
    claims = extract_claims(answer)
    if not claims:
        return GroundingMetrics(
            groundedness_score=1.0,
            groundedness_label="fully_grounded",
            supported_claims_ratio=1.0,
        )

    if not evidence_items:
        return GroundingMetrics(
            groundedness_score=0.0,
            groundedness_label="ungrounded",
            supported_claims_ratio=0.0,
        )

    # Build lookup map of evidence texts by evidence ID and overall concatenated text
    evidence_text_by_id: dict[str, str] = {}
    all_evidence_text_parts: list[str] = []

    for ev in evidence_items:
        ev_id = ev.get("evidence_id") or ev.get("id") or ""
        content = ev.get("content") or ev.get("text") or ""
        metadata = ev.get("metadata") or {}
        meta_str = " ".join(
            f"{k} {v}" for k, v in metadata.items() if isinstance(v, (str, int, float))
        )
        full_ev_text = f"{content} {meta_str}".strip().lower()

        if ev_id:
            evidence_text_by_id[ev_id.upper()] = full_ev_text
        all_evidence_text_parts.append(full_ev_text)

    combined_all = " ".join(all_evidence_text_parts)

    supported_count = 0

    for claim in claims:
        # Check if claim cites specific evidence [S1], [R1]
        cited_markers = re.findall(r"\[([A-Za-z0-9_-]+)\]", claim)
        target_context = ""

        if cited_markers:
            matching_texts = [
                evidence_text_by_id[m.upper()]
                for m in cited_markers
                if m.upper() in evidence_text_by_id
            ]
            if matching_texts:
                target_context = " ".join(matching_texts)

        if not target_context:
            target_context = combined_all

        # Check claim token overlap against target context
        claim_clean = re.sub(r"\[[A-Za-z0-9_-]+\]", "", claim).lower()
        tokens = set(re.findall(r"\b\w{3,}\b", claim_clean))
        if not tokens:
            supported_count += 1
            continue

        matched_tokens = sum(1 for tok in tokens if tok in target_context)
        overlap_ratio = matched_tokens / len(tokens)

        # Corroborated if >= 50% key content words exist in targeted evidence
        if overlap_ratio >= 0.5:
            supported_count += 1

    ratio = supported_count / len(claims)

    if ratio >= 0.85:
        score = 1.0
        label = "fully_grounded"
    elif ratio >= 0.30:
        score = 0.5
        label = "partially_grounded"
    else:
        score = 0.0
        label = "ungrounded"

    return GroundingMetrics(
        groundedness_score=score,
        groundedness_label=label,
        supported_claims_ratio=ratio,
    )
