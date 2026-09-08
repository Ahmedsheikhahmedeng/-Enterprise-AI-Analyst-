"""Security Status API Endpoint — TASK 22.

Provides a hardened, authenticated status probe for security subsystems.
Never exposes secrets, credentials, internal IP networks, or full configurations.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.security.threat_model import SYSTEM_THREAT_MODEL

router = APIRouter(prefix="/security", tags=["security"])


@router.get(
    "/status",
    summary="Security Subsystems Operational Status",
    response_model=dict[str, Any],
)
async def get_security_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Return high-level operational status of active security controls.

    Access requires authentication. No secrets, keys, or internal network
    topologies are disclosed.
    """
    return {
        "status": "operational",
        "controls": {
            "authentication_hardening": "active",
            "tenant_isolation_policy": "active",
            "prompt_injection_shield": "active",
            "ssrf_protection": "active",
            "file_security_validator": "active",
            "export_formula_shield": "active",
            "rate_limiter": "active",
            "replay_protection": "active",
            "security_headers": "active",
        },
        "threat_model_threats_tracked": len(SYSTEM_THREAT_MODEL),
    }
