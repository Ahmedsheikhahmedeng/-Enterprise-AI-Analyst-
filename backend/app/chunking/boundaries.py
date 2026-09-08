"""Boundary detection, heading hierarchy tracking, and sentence splitting.

Provides structure-aware heading path state management and deterministic
multilingual sentence boundary segmentation.
"""

import re
import unicodedata


class HeadingPathTracker:
    """Maintains an active heading stack to construct hierarchical heading paths.

    Tracks pairs of (level, title). When a new heading at level `L` is encountered,
    all headings at level >= `L` are popped, ensuring accurate nesting.
    """

    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def update(self, level: int, title: str) -> None:
        """Update tracker with a newly encountered heading."""
        cleaned_title = unicodedata.normalize("NFKC", title).strip()
        if not cleaned_title:
            return

        # Ensure valid level (default to 1 if <= 0)
        norm_level = max(1, level)

        # Pop any headings with level >= current heading level
        while self._stack and self._stack[-1][0] >= norm_level:
            self._stack.pop()

        self._stack.append((norm_level, cleaned_title))

    def reset(self) -> None:
        """Clear the heading stack."""
        self._stack.clear()

    @property
    def heading_path(self) -> list[str]:
        """Return the current hierarchical heading titles list."""
        return [title for _, title in self._stack]

    @property
    def heading_context(self) -> str:
        """Format the current heading path into a single context string."""
        path = self.heading_path
        if not path:
            return ""
        return " > ".join(path)


class SentenceSplitter:
    """Multilingual sentence boundary detector.

    Detects sentence ends while respecting abbreviations in English and Turkish,
    Arabic punctuation (؟, !, ., ؛), and numeric decimal formats.
    """

    # Common abbreviations across Turkish, English, and French
    _ABBREVIATIONS = {
        # English
        "mr.",
        "mrs.",
        "ms.",
        "dr.",
        "prof.",
        "sr.",
        "jr.",
        "vs.",
        "etc.",
        "e.g.",
        "i.e.",
        "fig.",
        "corp.",
        "inc.",
        "ltd.",
        "co.",
        "dept.",
        "univ.",
        # Turkish
        "vb.",
        "bkz.",
        "sf.",
        "av.",
        "doç.",
        "öğr.",
        "gör.",
        "müh.",
        "mim.",
        "cad.",
        "sok.",
        "apt.",
        "no.",
        "tel.",
        "mad.",
        "tc.",
    }

    # Sentence boundary regex: matches terminal punctuation followed by whitespace
    _BOUNDARY_REGEX = re.compile(
        r"([.!?؟؛]+)([\"'\u201d\u2019\])]*\s+)",
        re.UNICODE,
    )

    def split(self, text: str) -> list[str]:
        """Split text into sentences while preserving non-breaking abbreviations."""
        if not text or not text.strip():
            return []

        normalized = unicodedata.normalize("NFKC", text).strip()
        sentences: list[str] = []
        last_idx = 0

        for match in self._BOUNDARY_REGEX.finditer(normalized):
            punct = match.group(1)
            end_idx = match.end()

            # Preceding word check for abbreviation protection
            pre_boundary = normalized[last_idx : match.start(1)]
            words = pre_boundary.strip().split()
            last_word = words[-1].lower() + punct if words else ""

            # If it's a known abbreviation with a dot, skip split
            if punct == "." and last_word.lower() in self._ABBREVIATIONS:
                continue

            # Number check (e.g. "section 1. 2" or bullet "1. ")
            if (
                punct == "."
                and words
                and words[-1].isdigit()
                and len(words) == 1
                and len(pre_boundary.strip()) <= 3
            ):
                continue

            sentence = normalized[last_idx:end_idx].strip()
            if sentence:
                sentences.append(sentence)
            last_idx = end_idx

        # Append any remaining segment
        remaining = normalized[last_idx:].strip()
        if remaining:
            sentences.append(remaining)

        return sentences if sentences else [normalized]


# Global sentence splitter instance
default_sentence_splitter = SentenceSplitter()
