"""Multi-tiered adversarial Prompt Injection detection, classification, and containment engine."""

import re
from dataclasses import dataclass
from enum import StrEnum

from app.security.sanitization import normalize_security_text


class PromptRiskLevel(StrEnum):
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    HIGH_RISK = "high_risk"


@dataclass(frozen=True)
class PromptScanResult:
    """Outcome of adversarial prompt injection analysis."""

    is_safe: bool
    risk_level: str  # "benign", "suspicious", "high_risk"
    category: str
    risk_score: float  # 0.0 to 1.0
    matched_pattern: str | None = None

    @property
    def matches(self) -> list[str]:
        """Convenience property for list of matches."""
        return [self.matched_pattern] if self.matched_pattern else []


# High-Risk adversarial pattern definitions
HIGH_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|above|prior|initial)?\s*(?:instructions|prompts|rules|commands|system\s+prompt)",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt_leak",
        re.compile(
            r"(?:reveal|show|print|display|leak|output|repeat)\s+(?:the\s+|your\s+|all\s+)?(?:system\s+(?:prompt|instructions)|hidden\s+instructions|initial\s+prompt|developer\s+(?:message|prompts)|secret\s+instructions)",
            re.IGNORECASE,
        ),
    ),
    (
        "safety_bypass",
        re.compile(
            r"(?:disable|bypass|deactivate|turn\s+off)\s+(?:all\s+)?(?:safety|content\s+filters?|moderation|security\s+rules?|restrictions?|constraints?)",
            re.IGNORECASE,
        ),
    ),
    (
        "privilege_escalation",
        re.compile(
            r"(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:an?\s+)?(?:system\s+administrator|root|superuser|unrestricted\s+ai|developer\s+mode|dan)",
            re.IGNORECASE,
        ),
    ),
    (
        "exfiltration_attempt",
        re.compile(
            r"(?:send|exfiltrate|transmit|post)\s+(?:all\s+)?(?:secret\s+)?(?:secrets|credentials|passwords|api\s*keys?|tokens)\s+(?:to|via|using)",
            re.IGNORECASE,
        ),
    ),
)

# Suspicious patterns that warrant scrutiny or lower confidence
SUSPICIOUS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(r"\b(?:new\s+system\s+instructions|system\s*:\s*you\s+must)\b", re.IGNORECASE),
    ),
    (
        "system_prompt_leak",
        re.compile(
            r"\b(?:what\s+are\s+your\s+hidden\s+instructions|what\s+is\s+your\s+true\s+prompt)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak_marker",
        re.compile(r"\b(?:jailbreak|unfiltered\s+mode|do\s+anything\s+now)\b", re.IGNORECASE),
    ),
)


class PromptInjectionDetector:
    """Evaluates untrusted natural language inputs against adversarial prompt injection attacks."""

    def __init__(self, config: object = None) -> None:
        self.config = config

    def normalize(self, text: str) -> str:
        """Apply Unicode NFKC normalization, strip zero-width characters, and collapse spaces."""
        # 1. Remove zero-width spaces, soft hyphens, and word joiners used for obfuscation
        scrubbed = re.sub(r"[\u200b\u200c\u200d\ufeff\xad\u2060]", "", text)
        # 2. NFKC normalize
        norm = normalize_security_text(scrubbed)
        # 3. Collapse multiple whitespace
        return re.sub(r"\s+", " ", norm)

    def scan(self, text: str | None) -> PromptScanResult:
        """Scan input and classify into benign, suspicious, or high_risk without crashing."""
        if not text or not text.strip():
            return PromptScanResult(
                is_safe=True,
                risk_level="benign",
                category="none",
                risk_score=0.0,
            )

        normalized = self.normalize(text)

        # 1. Check High-Risk Patterns
        for category, pattern in HIGH_RISK_PATTERNS:
            match = pattern.search(normalized)
            if match:
                return PromptScanResult(
                    is_safe=False,
                    risk_level="high_risk",
                    category=category,
                    risk_score=0.95,
                    matched_pattern=match.group(0),
                )

        # 2. Check Suspicious Patterns
        for category, pattern in SUSPICIOUS_PATTERNS:
            match = pattern.search(normalized)
            if match:
                return PromptScanResult(
                    is_safe=True,  # Still allowed through but flagged as suspicious
                    risk_level="suspicious",
                    category=category,
                    risk_score=0.50,
                    matched_pattern=match.group(0),
                )

        # 3. Benign input
        return PromptScanResult(
            is_safe=True,
            risk_level="benign",
            category="normal",
            risk_score=0.05,
        )


# Global singleton
_global_prompt_detector: PromptInjectionDetector | None = None


def get_prompt_injection_detector() -> PromptInjectionDetector:
    """Singleton getter for PromptInjectionDetector."""
    global _global_prompt_detector
    if _global_prompt_detector is None:
        _global_prompt_detector = PromptInjectionDetector()
    return _global_prompt_detector
