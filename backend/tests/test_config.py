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
