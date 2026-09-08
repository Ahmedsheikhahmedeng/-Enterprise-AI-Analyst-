"""Production Security Package — TASK 22.

Provides unified security controls, threat modeling, tenant isolation,
prompt injection defense, SSRF protection, rate limiting, and auditing.
"""

from app.security.audit import (
    EVENT_AUTHZ_DENIED,
    EVENT_FILE_REJECTED,
    EVENT_JWT_REJECTED,
    EVENT_LOGIN_FAILED,
    EVENT_PROMPT_INJECTION,
    EVENT_RATE_LIMITED,
    EVENT_REPLAY_REJECTED,
    EVENT_SSRF_BLOCKED,
    EVENT_TENANT_VIOLATION,
    SecurityAuditEvent,
    SecurityAuditor,
)
from app.security.config import SecurityConfig
from app.security.context import (
    SecurityContext,
    clear_security_context,
    get_security_context,
    set_security_context,
)
from app.security.cors import get_hardened_cors_kwargs, validate_cors_origins
from app.security.exceptions import (
    ExportSecurityError,
    FileSecurityError,
    IDORViolationError,
    PromptInjectionDetectedError,
    RateLimitExceededError,
    ReplayViolationError,
    SecurityError,
    SecurityPolicyViolationError,
    SSRFBlockedError,
    TenantIsolationViolationError,
)
from app.security.export_security import sanitize_csv_cell, sanitize_export_filename
from app.security.file_security import FileSecurityValidator, ValidatedFile
from app.security.headers import SecurityHeadersMiddleware
from app.security.input_validation import SecurityInputValidator
from app.security.policies import TenantSecurityPolicy
from app.security.prompt_injection import (
    PromptInjectionDetector,
    PromptRiskLevel,
    PromptScanResult,
)
from app.security.rate_limit import RateLimiter, RateLimitResult
from app.security.replay import IdempotencyManager, IdempotencyRecord
from app.security.sanitization import (
    escape_html,
    normalize_security_text,
    sanitize_header_value,
)
from app.security.secrets import SecretSafeLogger
from app.security.service import SecurityService, get_security_service
from app.security.ssrf import SSRFProtection
from app.security.threat_model import SYSTEM_THREAT_MODEL, STRIDECategory, ThreatRecord

__all__ = [
    # Config & Context
    "SecurityConfig",
    "SecurityContext",
    "get_security_context",
    "set_security_context",
    "clear_security_context",
    # Exceptions
    "SecurityError",
    "SecurityPolicyViolationError",
    "PromptInjectionDetectedError",
    "SSRFBlockedError",
    "FileSecurityError",
    "ExportSecurityError",
    "RateLimitExceededError",
    "ReplayViolationError",
    "TenantIsolationViolationError",
    "IDORViolationError",
    # Controls & Services
    "SecurityService",
    "get_security_service",
    "TenantSecurityPolicy",
    "PromptInjectionDetector",
    "PromptScanResult",
    "PromptRiskLevel",
    "SSRFProtection",
    "FileSecurityValidator",
    "ValidatedFile",
    "SecurityInputValidator",
    "RateLimiter",
    "RateLimitResult",
    "IdempotencyManager",
    "IdempotencyRecord",
    "SecurityAuditor",
    "SecurityAuditEvent",
    "SecretSafeLogger",
    # Sanitization & Headers
    "escape_html",
    "normalize_security_text",
    "sanitize_header_value",
    "sanitize_csv_cell",
    "sanitize_export_filename",
    "SecurityHeadersMiddleware",
    "validate_cors_origins",
    "get_hardened_cors_kwargs",
    # Threat Model
    "SYSTEM_THREAT_MODEL",
    "STRIDECategory",
    "ThreatRecord",
    # Events
    "EVENT_LOGIN_FAILED",
    "EVENT_JWT_REJECTED",
    "EVENT_AUTHZ_DENIED",
    "EVENT_TENANT_VIOLATION",
    "EVENT_PROMPT_INJECTION",
    "EVENT_SSRF_BLOCKED",
    "EVENT_FILE_REJECTED",
    "EVENT_RATE_LIMITED",
    "EVENT_REPLAY_REJECTED",
]
