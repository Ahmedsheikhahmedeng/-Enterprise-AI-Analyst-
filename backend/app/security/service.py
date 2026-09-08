"""Central Security Service Façade — TASK 22.

Coordinates unified security policies and controls across the application:
- Input validation and sanitization
- Prompt injection detection and containment
- SSRF prevention
- File upload security
- Multi-tenant isolation enforcement
- Rate limiting and replay protection
- Security audit event dispatching
"""

from __future__ import annotations

from typing import Any

from app.security.audit import SecurityAuditEvent, SecurityAuditor
from app.security.config import SecurityConfig
from app.security.context import SecurityContext
from app.security.export_security import sanitize_csv_cell, sanitize_export_filename
from app.security.file_security import FileSecurityValidator, ValidatedFile
from app.security.input_validation import SecurityInputValidator
from app.security.policies import TenantSecurityPolicy
from app.security.prompt_injection import PromptInjectionDetector, PromptScanResult
from app.security.rate_limit import RateLimiter
from app.security.replay import IdempotencyManager
from app.security.ssrf import SSRFProtection


class SecurityService:
    """Central orchestration service for system-wide security hardening."""

    def __init__(
        self,
        config: SecurityConfig | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self.config = config or SecurityConfig()
        self.input_validator = SecurityInputValidator(self.config)
        self.prompt_detector = PromptInjectionDetector(self.config)
        self.ssrf_protection = SSRFProtection(self.config)
        self.file_validator = FileSecurityValidator(self.config)
        self.tenant_policy = TenantSecurityPolicy()
        self.rate_limiter = RateLimiter(redis_client=redis_client, config=self.config)
        self.idempotency_manager = IdempotencyManager(
            redis_client=redis_client, default_ttl_seconds=self.config.replay_window_seconds
        )
        self.auditor = SecurityAuditor()

    # --- Prompt Injection Shield ---
    def scan_prompt(self, text: str, user_id: str | None = None) -> PromptScanResult:
        """Scan text for prompt injection patterns."""
        return self.prompt_detector.scan(text)

    # --- SSRF Shield ---
    def validate_url(self, url: str) -> str:
        """Validate destination URL against SSRF policy."""
        return self.ssrf_protection.validate_url(url)

    # --- File Upload Shield ---
    def validate_upload(
        self,
        filename: str,
        content: bytes,
        claimed_mime: str | None = None,
    ) -> ValidatedFile:
        """Validate uploaded file bytes, magic headers, and extension."""
        return self.file_validator.validate_file(
            filename=filename,
            content=content,
            claimed_mime=claimed_mime,
        )

    # --- Export Shield ---
    @staticmethod
    def sanitize_cell(value: Any) -> str:
        """Neutralize CSV formula injection."""
        return sanitize_csv_cell(value)

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize export filename against path traversal and CRLF."""
        return sanitize_export_filename(filename, max_length=self.config.max_export_filename_length)

    # --- Audit Shield ---
    async def record_audit_event(self, event: SecurityAuditEvent) -> None:
        """Emit security audit telemetry and structured log."""
        await self.auditor.record_event(event)

    # --- Tenant Shield ---
    def assert_tenant_access(
        self,
        context: SecurityContext,
        resource: Any,
        resource_type: str = "resource",
    ) -> None:
        """Enforce tenant boundary on domain resources."""
        self.tenant_policy.require_tenant_resource(
            context=context,
            resource=resource,
            resource_type=resource_type,
        )


# Global singleton security service
_global_security_service: SecurityService | None = None


def get_security_service(
    config: SecurityConfig | None = None,
    redis_client: Any | None = None,
) -> SecurityService:
    """Get or instantiate global SecurityService singleton."""
    global _global_security_service
    if _global_security_service is None:
        _global_security_service = SecurityService(config=config, redis_client=redis_client)
    return _global_security_service
