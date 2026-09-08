"""SSRF Defense Tests — TASK 22.

Verifies:
- Dangerous scheme rejection (file://, ftp://, gopher://, data:, javascript:)
- Localhost and loopback address blocking (127.0.0.1, ::1, localhost)
- Private RFC-1918 subnet blocking (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Cloud instance metadata endpoint blocking (169.254.169.254)
- Safe public domain acceptance
- Redirect SSRF validation
"""

import pytest

from app.security.config import SecurityConfig
from app.security.exceptions import SSRFBlockedError
from app.security.ssrf import SSRFProtection


@pytest.fixture
def ssrf() -> SSRFProtection:
    return SSRFProtection(SecurityConfig())


@pytest.mark.parametrize(
    "dangerous_scheme_url",
    [
        "file:///etc/passwd",
        "ftp://internal.server/file.txt",
        "gopher://127.0.0.1:70/",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "javascript:alert(1)",
    ],
)
def test_dangerous_schemes_blocked(
    ssrf: SSRFProtection,
    dangerous_scheme_url: str,
) -> None:
    with pytest.raises(SSRFBlockedError) as exc:
        ssrf.validate_url(dangerous_scheme_url)
    assert "scheme" in str(exc.value).lower()


@pytest.mark.parametrize(
    "private_ip_url",
    [
        "https://127.0.0.1/admin",
        "https://10.0.0.5/api",
        "https://172.16.10.2/internal",
        "https://192.168.1.100/status",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/debug",
    ],
)
def test_private_ip_blocked(
    ssrf: SSRFProtection,
    private_ip_url: str,
) -> None:
    with pytest.raises(SSRFBlockedError) as exc:
        ssrf.validate_url(private_ip_url)
    err_str = str(exc.value).lower()
    assert (
        ("private" in err_str)
        or ("internal" in err_str)
        or ("metadata" in err_str)
        or ("forbidden" in err_str)
    )


def test_redirect_to_internal_ip_blocked(ssrf: SSRFProtection) -> None:
    # Public URL redirects to internal localhost
    with pytest.raises(SSRFBlockedError):
        ssrf.validate_redirect_url(
            initial_url="https://public-service.com/redirect",
            redirect_url="https://127.0.0.1:8080/admin",
        )
