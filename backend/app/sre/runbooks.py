"""Runbook safety validation and immutable versioning."""

import re

DANGEROUS_COMMAND_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdrop\s+table\b",
    r"\bdrop\s+database\b",
    r"\btruncate\b",
    r"\bkill\s+-9\b",
    r"\bdelete\s+from\b\s+[^w]",  # DELETE without WHERE or blanket DELETE
    r"\bformat\s+c:\b",
    r"\bdd\s+if=",
]


class UnsafeRunbookActionError(Exception):
    """Raised when a runbook action contains forbidden destructive commands."""

    def __init__(self, step: str, pattern: str):
        super().__init__(
            f"Runbook action contains forbidden destructive command pattern '{pattern}': '{step}'. "
            f"SRE safety policy forbids destructive shell and SQL commands in automated or manual runbooks."
        )
        self.step = step
        self.pattern = pattern


class PublishedRunbookImmutableError(Exception):
    """Raised when an attempt is made to mutate a published runbook in-place without bumping version."""

    def __init__(self, runbook_name: str, version: int):
        super().__init__(
            f"Runbook '{runbook_name}' version {version} is published and immutable. "
            f"Please create a new draft version rather than mutating a published runbook."
        )


def validate_runbook_safety(steps: list[str]) -> None:
    """Scan diagnostic and safe action steps to ensure NO destructive commands are present."""
    for step in steps:
        step_lower = step.lower()
        for pat in DANGEROUS_COMMAND_PATTERNS:
            if re.search(pat, step_lower):
                raise UnsafeRunbookActionError(step, pat)
