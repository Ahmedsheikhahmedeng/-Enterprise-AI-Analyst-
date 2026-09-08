"""Central security configuration for production hardening, rate limits, and threat defenses."""

from dataclasses import dataclass, field
from functools import lru_cache

from app.core.config import get_settings


@dataclass(frozen=True)
class SecurityConfig:
    """Immutable security baseline configuration defining constraints, allowlists, and thresholds."""

    # 1. JWT & Authentication
    jwt_allowed_algorithms: tuple[str, ...] = ("HS256",)
    jwt_clock_skew_seconds: int = 10
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

    # 2. Request & Payload Size Limits
    max_request_body_bytes: int = 10 * 1024 * 1024  # 10 MB JSON payload
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB Document upload
    max_query_length_chars: int = 4000  # 4000 chars for natural language query
    max_header_size_bytes: int = 16 * 1024  # 16 KB total headers
    max_export_rows: int = 50_000

    # 3. Rate Limits (requests per minute)
    rate_limit_login: int = 5
    rate_limit_register: int = 5
    rate_limit_refresh: int = 15
    rate_limit_analyst: int = 30
    rate_limit_upload: int = 20
    rate_limit_export: int = 20
    rate_limit_eval_run: int = 5
    rate_limit_default: int = 120

    # 4. Replay & Idempotency
    replay_window_seconds: int = 86_400  # 24 Hours idempotency retention

    # 5. SSRF & Network Protections
    allowed_schemes: tuple[str, ...] = ("https",)
    blocked_ip_cidrs: tuple[str, ...] = (
        "127.0.0.0/8",  # Localhost
        "10.0.0.0/8",  # RFC 1918 Private
        "172.16.0.0/12",  # RFC 1918 Private
        "192.168.0.0/16",  # RFC 1918 Private
        "169.254.0.0/16",  # Link-Local & Cloud Metadata
        "::1/128",  # IPv6 Loopback
        "fc00::/7",  # IPv6 Unique Local
        "fe80::/10",  # IPv6 Link-Local
    )
    cloud_metadata_hosts: tuple[str, ...] = (
        "169.254.169.254",
        "metadata.google.internal",
        "metadata.azure.com",
    )

    # 6. File Security
    allowed_upload_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset({"pdf", "docx", "txt", "csv", "xlsx"})
    )
    forbidden_upload_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"exe", "dll", "so", "sh", "bat", "cmd", "js", "html", "htm", "svg", "php", "py", "vbs"}
        )
    )

    # 7. SQL Resource Abuse Bounding
    sql_max_joins: int = 5
    sql_max_nesting_depth: int = 3
    sql_max_in_items: int = 100
    sql_max_unions: int = 2
    sql_statement_timeout_ms: int = 10_000

    # 8. CORS & Security Headers
    cors_allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    hsts_enabled: bool = False
    enable_hsts: bool = False
    hsts_force: bool = False
    hsts_include_subdomains: bool = True
    hsts_max_age_seconds: int = 31_536_000
    max_export_filename_length: int = 128
    max_request_body_size_bytes: int = 10 * 1024 * 1024


@lru_cache(maxsize=1)
def get_security_config() -> SecurityConfig:
    """Produce cached singleton instance of SecurityConfig."""
    settings = get_settings()
    is_prod = getattr(settings, "is_production", False)
    return SecurityConfig(
        hsts_enabled=is_prod,
    )
