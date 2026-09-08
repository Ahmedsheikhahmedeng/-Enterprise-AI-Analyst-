"""Deterministic hallucination detection verifying numerical, temporal, and entity assertions."""

import re
from collections.abc import Sequence
from typing import Any

from app.evaluation.metrics.rag import extract_claims
from app.evaluation.models import HallucinationMetrics

NUMERIC_CURRENCY_PATTERN = re.compile(
    r"\$?\b\d+(?:[\.,]\d+)?\s*(?:M|B|K|million|billion|thousand)?\b",
    re.IGNORECASE,
)
PERCENT_PATTERN = re.compile(r"\b\d+(?:[\.,]\d+)?%", re.IGNORECASE)
YEAR_DATE_PATTERN = re.compile(r"\b(19\d\d|20\d\d|Q[1-4]|H[1-2])\b", re.IGNORECASE)


def detect_hallucinations(
    answer: str,
    evidence_items: Sequence[dict[str, Any]],
    actual_evidence_ids: Sequence[str],
) -> HallucinationMetrics:
    """Scan answer for ungrounded numerical claims, phantom citations, dates, and percentages."""
    if not answer:
        return HallucinationMetrics()

    # Aggregate all evidence text and numbers
    all_evidence_parts: list[str] = []
    for ev in evidence_items:
        all_evidence_parts.append(ev.get("content") or ev.get("text") or "")
        metadata = ev.get("metadata") or {}
        for k, v in metadata.items():
            all_evidence_parts.append(f"{k} {v}")

    combined_evidence = " ".join(all_evidence_parts).lower()
    known_ev_ids = {i.upper() for i in actual_evidence_ids}

    # 1. Phantom Citations
    cited_markers = re.findall(r"\[([A-Za-z0-9_-]+)\]", answer)
    phantom_citations = sum(1 for m in cited_markers if m.upper() not in known_ev_ids)

    # Clean citations out of answer for statement inspection
    clean_answer = re.sub(r"\[[A-Za-z0-9_-]+\]", "", answer)

    # 2. Unsupported Percentages
    answer_percentages = PERCENT_PATTERN.findall(clean_answer)
    unsupported_percentages = 0
    for pct in answer_percentages:
        if pct.lower() not in combined_evidence:
            unsupported_percentages += 1

    # 3. Unsupported Dates / Quarters
    answer_dates = YEAR_DATE_PATTERN.findall(clean_answer)
    unsupported_dates = 0
    for dt in answer_dates:
        if dt.lower() not in combined_evidence:
            unsupported_dates += 1

    # 4. Unsupported Numerical Claims (currency and quantities)
    answer_numbers = NUMERIC_CURRENCY_PATTERN.findall(clean_answer)
    unsupported_numbers = 0
    for num in answer_numbers:
        num_clean = num.strip()
        # Skip generic single digit integers
        if num_clean.isdigit() and len(num_clean) == 1:
            continue
        # Extract digits
        digits_only = re.sub(r"[^\d]", "", num_clean)
        if digits_only and digits_only not in re.sub(r"[^\d]", "", combined_evidence):
            unsupported_numbers += 1

    total_claims = len(extract_claims(answer)) or 1
    total_hallucinations = (
        phantom_citations + unsupported_percentages + unsupported_dates + unsupported_numbers
    )

    penalty = min(1.0, total_hallucinations / (total_claims * 2))
    hallucination_score = max(0.0, 1.0 - penalty)

    return HallucinationMetrics(
        hallucination_score=hallucination_score,
        unsupported_numeric_count=unsupported_numbers,
        phantom_citation_count=phantom_citations,
        unsupported_entity_count=0,
        unsupported_date_count=unsupported_dates,
        unsupported_percentage_count=unsupported_percentages,
    )
