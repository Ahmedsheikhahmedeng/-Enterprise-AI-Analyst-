import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_settings() -> None:
    """Verify default settings instantiation and property evaluations."""
    settings = Settings()
    assert settings.APP_NAME == "Enterprise AI Analyst API"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert isinstance(settings.CORS_ORIGINS, list)


def test_cors_origins_parsing_from_string() -> None:
    """Verify comma-separated string in CORS_ORIGINS is parsed into list."""
    settings = Settings(CORS_ORIGINS="http://localhost:3000,http://app.internal:8080")  # type: ignore[arg-type]
    assert settings.CORS_ORIGINS == ["http://localhost:3000", "http://app.internal:8080"]


def test_environment_flags() -> None:
    """Verify environment boolean helper properties."""
    dev_settings = Settings(ENVIRONMENT="development")
    assert dev_settings.is_development is True
    assert dev_settings.is_production is False
    assert dev_settings.is_testing is False

    prod_settings = Settings(ENVIRONMENT="production")
    assert prod_settings.is_production is True
    assert prod_settings.is_development is False

    test_settings = Settings(ENVIRONMENT="testing")
    assert test_settings.is_testing is True


def test_invalid_environment_raises_validation_error() -> None:
    """Verify invalid environment string raises Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(ENVIRONMENT="invalid_environment")  # type: ignore[arg-type]
    assert "ENVIRONMENT" in str(exc_info.value)


def test_invalid_log_level_raises_validation_error() -> None:
    """Verify invalid log level raises Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(LOG_LEVEL="TRACE")  # type: ignore[arg-type]
    assert "LOG_LEVEL" in str(exc_info.value)


def test_infrastructure_settings_defaults() -> None:
    """Verify default infrastructure settings."""
    settings = Settings()
    assert "postgresql+asyncpg://" in settings.DATABASE_URL
    assert settings.DATABASE_POOL_SIZE == 10
    assert settings.DATABASE_MAX_OVERFLOW == 20
    assert "redis://" in settings.REDIS_URL
    assert settings.QDRANT_URL == "http://localhost:6333"
    assert settings.QDRANT_API_KEY is None


def test_sanitized_urls_redact_passwords() -> None:
    """Verify passwords are masked in sanitized URL properties to prevent log leaks."""
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://admin:super_secret_pw@db.internal:5432/app_db",
        REDIS_URL="redis://:secret_redis_pass@redis.internal:6379/0",
    )
    assert "super_secret_pw" not in settings.sanitized_database_url
    assert "admin:***@db.internal:5432" in settings.sanitized_database_url

    assert "secret_redis_pass" not in settings.sanitized_redis_url
    assert ":***@redis.internal:6379" in settings.sanitized_redis_url
