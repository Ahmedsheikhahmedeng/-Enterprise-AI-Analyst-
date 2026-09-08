"""Production Secret Management Abstraction supporting Docker secrets, env vars, and external vaults."""

import os
from collections.abc import Callable
from pathlib import Path

from app.connectors.infrastructure.secrets import SecretProvider
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger("core.secrets")

DEFAULT_DOCKER_SECRETS_PATH = Path("/run/secrets")


class ProductionSecretProvider(SecretProvider):
    """Production-grade secret provider resolving credentials hierarchically:

    1. External secret resolver hook (e.g. HashiCorp Vault, AWS Secrets Manager)
    2. File-based Docker Secrets (/run/secrets/<name>)
    3. OS Environment variables
    4. Optional default fallback

    Also retains symmetric encryption-at-rest and configuration redaction capabilities.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        secrets_dir: Path | str | None = None,
        external_resolver: Callable[[str], str | None] | None = None,
    ) -> None:
        super().__init__(settings=settings)
        self.secrets_dir = Path(secrets_dir) if secrets_dir else DEFAULT_DOCKER_SECRETS_PATH
        self.external_resolver = external_resolver
        self._secret_cache: dict[str, str] = {}

    def get_secret(self, secret_name: str, default: str | None = None) -> str | None:
        """Resolve a secret value by name across supported backends."""
        # 0. Check in-memory cache
        if secret_name in self._secret_cache:
            return self._secret_cache[secret_name]

        # 1. External Secret Manager resolver hook
        if self.external_resolver:
            try:
                val = self.external_resolver(secret_name)
                if val is not None:
                    self._secret_cache[secret_name] = val
                    return val
            except Exception as exc:
                logger.warning(
                    "External secret resolver failed, falling back",
                    secret_name=secret_name,
                    error=str(exc),
                )

        # 2. Docker Secrets file (/run/secrets/<secret_name>)
        secret_file = self.secrets_dir / secret_name
        if secret_file.is_file():
            try:
                secret_val = secret_file.read_text(encoding="utf-8").strip()
                if secret_val:
                    self._secret_cache[secret_name] = secret_val
                    return secret_val
            except Exception as exc:
                logger.warning(
                    "Failed to read Docker secret file",
                    file=str(secret_file),
                    error=str(exc),
                )

        # 3. Environment Variable lookup
        env_val = os.environ.get(secret_name)
        if env_val is not None:
            self._secret_cache[secret_name] = env_val
            return env_val

        # 4. Fallback default
        return default

    def resolve_required_secret(self, secret_name: str) -> str:
        """Retrieve a required secret or raise ValueError if unresolvable."""
        val = self.get_secret(secret_name)
        if val is None or not val.strip():
            raise ValueError(
                f"Required production secret '{secret_name}' could not be resolved from "
                f"external provider, Docker secrets ({self.secrets_dir}), or environment."
            )
        return val

    def set_external_resolver(self, resolver: Callable[[str], str | None]) -> None:
        """Register or override external secrets resolver dynamically."""
        self.external_resolver = resolver
        self._secret_cache.clear()


_global_production_secret_provider: ProductionSecretProvider | None = None


def get_production_secret_provider() -> ProductionSecretProvider:
    """Return cached singleton instance of ProductionSecretProvider."""
    global _global_production_secret_provider
    if _global_production_secret_provider is None:
        _global_production_secret_provider = ProductionSecretProvider()
    return _global_production_secret_provider
