"""Query safety, bounds validation, and prompt injection mitigation."""

import re

from app.query.exceptions import QuerySafetyError, QueryValidationError


class QuerySafetyValidator:
    """Validates query bounds and mitigates adversarial prompt injection patterns."""

    MIN_QUERY_LENGTH = 1
    MAX_QUERY_LENGTH = 1000
    MAX_TOKENS_ESTIMATE = 250

    # Common prompt injection triggers to sanitize
    _ADVERSARIAL_PATTERNS = [
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?", re.IGNORECASE),
        re.compile(r"system\s+prompt", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"bypass\s+security", re.IGNORECASE),
        re.compile(r"reveal\s+tenant", re.IGNORECASE),
        re.compile(r"drop\s+table", re.IGNORECASE),
        re.compile(r"--\s*$", re.MULTILINE),
    ]

    def validate_and_sanitize(self, raw_query: str) -> str:
        """Validate length bounds and return sanitized query string.

        Raises:
            QueryValidationError: If query is blank or exceeds maximum length.
            QuerySafetyError: If query contains unrecoverable binary/control sequences.
        """
        if raw_query is None:
            raise QueryValidationError("Query must not be None.")

        query = raw_query.strip()
        if len(query) < self.MIN_QUERY_LENGTH:
            raise QueryValidationError("Query must contain at least 1 non-whitespace character.")

        if len(query) > self.MAX_QUERY_LENGTH:
            raise QueryValidationError(
                f"Query length {len(query)} exceeds maximum allowed {self.MAX_QUERY_LENGTH} chars."
            )

        # Estimate tokens by whitespace separation
        word_count = len(query.split())
        if word_count > self.MAX_TOKENS_ESTIMATE:
            msg = f"Query tokens {word_count} exceeds safe ceiling {self.MAX_TOKENS_ESTIMATE}."
            raise QueryValidationError(msg)

        # Check for binary null bytes
        if "\x00" in query:
            raise QuerySafetyError("Query contains prohibited null byte characters.")

        # Neutralize potential prompt injection attempts by neutralizing instruction phrases
        sanitized = query
        for pattern in self._ADVERSARIAL_PATTERNS:
            if pattern.search(sanitized):
                # We replace the adversarial trigger phrase with benign text
                sanitized = pattern.sub("[filtered instruction]", sanitized)

        return sanitized
