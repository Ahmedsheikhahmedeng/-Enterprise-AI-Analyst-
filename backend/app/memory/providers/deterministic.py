"""Deterministic, reproducible memory extraction provider for test and production environments."""

import re

from app.memory.schemas import (
    MemoryCandidate,
    MemoryPrivacyLevel,
    MemorySourceType,
    MemoryType,
    MemoryVisibility,
)

PREFERENCE_PATTERNS = [
    r"(?:prefer|prefers|preference for)\s+([^.]+)",
    r"(?:always use|format as|wants to see)\s+([^.]+)",
]

POLICY_PATTERNS = [
    r"(?:policy is|rule is|fiscal year starts? in)\s+([^.]+)",
    r"(?:standard is|requirement is)\s+([^.]+)",
]

METRIC_PATTERNS = [
    r"(?:revenue|churn|growth|arr|retention)\s+(?:was|is|reached|increased by|decreased by)\s+([^.]+)",
]


class DeterministicMemoryExtractor:
    """Extracts structured memory candidates via deterministic regex and rule heuristics."""

    async def extract_candidates(
        self,
        context_text: str,
        source_type: MemorySourceType = MemorySourceType.AGENT_DERIVED,
        source_id: str | None = None,
    ) -> list[MemoryCandidate]:
        """Parse context text and emit structured candidates."""
        candidates: list[MemoryCandidate] = []
        if not context_text:
            return candidates

        sentences = re.split(r"[.!?\n]+", context_text)
        for sent in sentences:
            s_clean = sent.strip()
            if len(s_clean) < 10:
                continue

            # Check preferences
            for pat in PREFERENCE_PATTERNS:
                if re.search(pat, s_clean, re.IGNORECASE):
                    candidates.append(
                        MemoryCandidate(
                            memory_type=MemoryType.SEMANTIC,
                            content=s_clean,
                            summary=f"User preference: {s_clean[:100]}",
                            importance=0.75,
                            confidence=0.90,
                            source_type=source_type,
                            source_id=source_id,
                            visibility=MemoryVisibility.USER,
                            privacy_level=MemoryPrivacyLevel.NORMAL,
                        )
                    )
                    break

            # Check policies
            for pat in POLICY_PATTERNS:
                if re.search(pat, s_clean, re.IGNORECASE):
                    candidates.append(
                        MemoryCandidate(
                            memory_type=MemoryType.SEMANTIC,
                            content=s_clean,
                            summary=f"Organizational policy: {s_clean[:100]}",
                            importance=0.85,
                            confidence=0.95,
                            source_type=source_type,
                            source_id=source_id,
                            visibility=MemoryVisibility.ORGANIZATION,
                            privacy_level=MemoryPrivacyLevel.NORMAL,
                        )
                    )
                    break

            # Check metrics
            for pat in METRIC_PATTERNS:
                if re.search(pat, s_clean, re.IGNORECASE):
                    candidates.append(
                        MemoryCandidate(
                            memory_type=MemoryType.EPISODIC,
                            content=s_clean,
                            summary=f"Analytical metric fact: {s_clean[:100]}",
                            importance=0.70,
                            confidence=0.85,
                            source_type=source_type,
                            source_id=source_id,
                            visibility=MemoryVisibility.ORGANIZATION,
                            privacy_level=MemoryPrivacyLevel.NORMAL,
                        )
                    )
                    break

        return candidates
