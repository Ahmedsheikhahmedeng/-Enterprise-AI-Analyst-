"""Security, tenant isolation, and authorization policies for background jobs."""

import json
import uuid
from typing import Any

from app.jobs.config import job_config
from app.jobs.exceptions import JobPayloadTooLargeError
from app.jobs.models import Job
from app.security.exceptions import SecurityPolicyViolationError
from app.security.policies import TenantSecurityPolicy

# Forbidden substrings in payload keys or string values to prevent accidental secret leakage
FORBIDDEN_SECRET_KEYWORDS = (
    "password",
    "secret_key",
    "private_key",
    "access_token",
    "refresh_token",
    "authorization",
    "jwt",
    "api_key",
    "apikey",
    "secret",
    "token",
)


class JobSecurityPolicy:
    """Security validations for job payloads and tenant authorization."""

    @classmethod
    def assert_tenant_access(cls, context_org_id: uuid.UUID | str | None, job: Job) -> None:
        """Assert that tenant context matches the job's owning organization."""
        TenantSecurityPolicy.assert_same_tenant(
            context_org_id=context_org_id,
            resource_org_id=job.organization_id,
            resource_type="job",
            resource_id=job.id,
        )

    @classmethod
    def validate_payload(cls, payload: dict[str, Any]) -> None:
        """Validate payload size limits and ensure no plain credentials are stored."""
        # 1. Check serialized payload size
        serialized = json.dumps(payload, default=str)
        size_bytes = len(serialized.encode("utf-8"))
        if size_bytes > job_config.MAX_PAYLOAD_BYTES:
            raise JobPayloadTooLargeError(size_bytes, job_config.MAX_PAYLOAD_BYTES)

        # 2. Check for prohibited secret-bearing keys
        def _scan_secrets(data: Any) -> None:
            if isinstance(data, dict):
                for k, v in data.items():
                    k_lower = str(k).lower()
                    if any(bad in k_lower for bad in FORBIDDEN_SECRET_KEYWORDS):
                        raise SecurityPolicyViolationError(
                            f"Prohibited sensitive field '{k}' detected in background job payload. "
                            "Do not store credentials or secrets in job payloads."
                        )
                    _scan_secrets(v)
            elif isinstance(data, list):
                for item in data:
                    _scan_secrets(item)

        _scan_secrets(payload)
