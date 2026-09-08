"""Unit tests for Production Security, Configuration Validation, and Secret Management."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.secrets import ProductionSecretProvider


def test_production_rejects_debug_mode() -> None:
    """Verify that Settings raises ValidationError if DEBUG is True in production."""
    with pytest.raises(ValidationError, match="DEBUG mode must be disabled"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            JWT_SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+asyncpg://user:pass@dbserver:5432/proddb",
            REDIS_URL="redis://:pass@redisserver:6379/0",
            QDRANT_URL="http://qdrant:6333",
        )


def test_production_rejects_wildcard_cors() -> None:
    """Verify that Settings raises ValidationError if CORS contains '*' in production."""
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            CORS_ORIGINS=["*"],
            JWT_SECRET_KEY="b" * 32,
            DATABASE_URL="postgresql+asyncpg://user:pass@dbserver:5432/proddb",
            REDIS_URL="redis://:pass@redisserver:6379/0",
            QDRANT_URL="http://qdrant:6333",
        )


def test_production_rejects_weak_or_default_secrets() -> None:
    """Verify that Settings rejects dev-insecure, change-me, or short JWT keys in production."""
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_SECRET_KEY="dev-insecure-secret-key-too-short",
            DATABASE_URL="postgresql+asyncpg://user:pass@dbserver:5432/proddb",
            REDIS_URL="redis://:pass@redisserver:6379/0",
            QDRANT_URL="http://qdrant:6333",
        )

    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_SECRET_KEY="change-me-production-secret-12345",
            DATABASE_URL="postgresql+asyncpg://user:pass@dbserver:5432/proddb",
            REDIS_URL="redis://:pass@redisserver:6379/0",
            QDRANT_URL="http://qdrant:6333",
        )


def test_production_rejects_default_local_database() -> None:
    """Verify that Settings rejects default localhost postgres in production."""
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            JWT_SECRET_KEY="c" * 32,
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai_analyst",
            REDIS_URL="redis://:pass@redisserver:6379/0",
            QDRANT_URL="http://qdrant:6333",
        )


def test_production_valid_configuration() -> None:
    """Verify that a compliant production configuration instantiates cleanly."""
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        CORS_ORIGINS=["https://analyst.enterprise.internal"],
        JWT_SECRET_KEY="strong-high-entropy-production-secret-1234567890",
        DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@pgserver:5432/proddb",
        REDIS_URL="redis://:prod_redis_pass@redisserver:6379/0",
        QDRANT_URL="http://qdrantserver:6333",
    )
    assert settings.is_production is True
    assert settings.DEBUG is False
    assert "*" not in settings.CORS_ORIGINS


def test_production_secret_provider_hierarchy(tmp_path: Path) -> None:
    """Verify ProductionSecretProvider hierarchy: External -> Docker secrets -> Env -> Default."""
    # 1. Setup Docker secret file
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    (secret_dir / "db_password").write_text("docker-secret-pass\n", encoding="utf-8")

    provider = ProductionSecretProvider(secrets_dir=secret_dir)

    # Resolve from Docker secret file
    assert provider.get_secret("db_password") == "docker-secret-pass"

    # Resolve from environment
    os.environ["API_KEY_ENV"] = "env-secret-value"
    assert provider.get_secret("API_KEY_ENV") == "env-secret-value"

    # Resolve default fallback
    assert provider.get_secret("UNKNOWN_KEY", default="default-val") == "default-val"

    # Resolve via external resolver hook
    provider.set_external_resolver(lambda key: "vault-secret" if key == "vault_key" else None)
    assert provider.get_secret("vault_key") == "vault-secret"
