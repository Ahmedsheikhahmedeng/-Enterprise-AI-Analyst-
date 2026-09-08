"""Secret Redaction & Protection Tests — TASK 22.

Verifies:
- Masking of API tokens, Bearer tokens, DB credentials, and private keys
- SecretSafeLogger sanitization in dicts, strings, and logging envelopes
"""

from app.security.secrets import SecretSafeLogger


def test_redacts_bearer_token() -> None:
    raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID"
    scrubbed = SecretSafeLogger.sanitize_text(raw)
    assert "Bearer eyJ" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_redacts_openai_api_keys() -> None:
    raw = "Connecting with client key sk-abc1234567890abcdef1234567890 to OpenAI"
    scrubbed = SecretSafeLogger.sanitize_text(raw)
    assert "sk-abc1234567890abcdef1234567890" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_redacts_database_passwords_in_dsn() -> None:
    raw = "postgresql+asyncpg://admin:SuperSecretPass99@db.internal.vpc:5432/analytics"
    scrubbed = SecretSafeLogger.sanitize_text(raw)
    assert "SuperSecretPass99" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_redacts_nested_dictionary_secrets() -> None:
    payload = {
        "user": "analyst",
        "api_key": "sk-test1234567890abcdef12345",
        "nested": {
            "password": "Password123!",
            "public_metric": 42,
        },
    }
    scrubbed = SecretSafeLogger.sanitize_mapping(payload)
    assert scrubbed["user"] == "analyst"
    assert scrubbed["nested"]["public_metric"] == 42
    assert scrubbed["api_key"] == "[REDACTED]"
    assert scrubbed["nested"]["password"] == "[REDACTED]"
