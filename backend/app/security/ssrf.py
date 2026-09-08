"""Server-Side Request Forgery (SSRF) defense engine enforcing network boundary isolation."""

import ipaddress
import socket
import urllib.parse
from urllib.parse import urlparse

from app.security.config import SecurityConfig, get_security_config
from app.security.exceptions import SSRFBlockedError


class SSRFProtection:
    """Validates outbound URLs to strictly prevent requests to loopback, private, or metadata networks."""

    def __init__(self, config: SecurityConfig | None = None) -> None:
        self.config = config or get_security_config()
        self._blocked_networks = [
            ipaddress.ip_network(cidr) for cidr in self.config.blocked_ip_cidrs
        ]

    def is_ip_blocked(self, ip_str: str) -> bool:
        """Check whether a resolved IPv4/IPv6 address falls within forbidden private or link-local CIDRs."""
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return True

        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_reserved:
            return True

        return any(ip_obj in net for net in self._blocked_networks)

    def validate_url(self, target_url: str) -> str:
        """Thoroughly validate target URL scheme, host, and resolved IP against SSRF policies."""
        if not target_url or not target_url.strip():
            raise SSRFBlockedError(
                message="URL cannot be empty.", target_host="empty", reason="empty_url"
            )

        clean_url = target_url.strip()
        try:
            parsed = urlparse(clean_url)
        except Exception as exc:
            raise SSRFBlockedError(
                message="Malformed URL string provided.",
                target_host="malformed",
                reason="malformed_url",
            ) from exc

        # 1. Scheme Validation
        scheme = parsed.scheme.lower()
        if scheme not in self.config.allowed_schemes:
            raise SSRFBlockedError(
                message=f"Forbidden URL scheme '{scheme}'. Only HTTPS is permitted.",
                target_host=parsed.netloc,
                reason="forbidden_scheme",
            )

        # 2. Hostname Validation
        hostname = parsed.hostname
        if not hostname:
            raise SSRFBlockedError(
                message="URL missing valid hostname.",
                target_host="none",
                reason="missing_hostname",
            )

        clean_host = hostname.lower().strip()

        # Check metadata hostnames
        if clean_host in self.config.cloud_metadata_hosts:
            raise SSRFBlockedError(
                message="Access to cloud metadata endpoints is strictly blocked.",
                target_host=clean_host,
                reason="cloud_metadata_access",
            )

        # 3. Direct IP Check
        try:
            # If hostname is already a numeric IP address
            direct_ip = ipaddress.ip_address(clean_host)
            if self.is_ip_blocked(str(direct_ip)):
                raise SSRFBlockedError(
                    message=f"Direct access to private/internal IP {direct_ip} is forbidden.",
                    target_host=clean_host,
                    reason="private_ip_forbidden",
                )
            return clean_url
        except ValueError:
            pass  # Hostname is a domain name, proceed to DNS resolution check

        # 4. DNS Resolution & Rebinding Protection
        try:
            addr_info = socket.getaddrinfo(clean_host, None)
        except socket.gaierror as exc:
            raise SSRFBlockedError(
                message=f"Failed to resolve DNS hostname '{clean_host}'.",
                target_host=clean_host,
                reason="dns_resolution_failed",
            ) from exc

        for entry in addr_info:
            sockaddr = entry[4]
            resolved_ip = str(sockaddr[0])
            if self.is_ip_blocked(resolved_ip):
                raise SSRFBlockedError(
                    message=f"Hostname '{clean_host}' resolves to prohibited internal IP {resolved_ip}.",
                    target_host=clean_host,
                    reason="resolved_to_private_ip",
                )

        return clean_url

    def validate_redirect(self, current_url: str, redirect_url: str) -> str:
        """Validate redirect target URL ensuring redirect chains cannot bypass SSRF rules."""
        resolved_redirect = urllib.parse.urljoin(current_url, redirect_url)
        return self.validate_url(resolved_redirect)

    def validate_redirect_url(self, initial_url: str, redirect_url: str) -> str:
        """Alias for validate_redirect."""
        return self.validate_redirect(initial_url, redirect_url)


# Global singleton
_global_ssrf_protection: SSRFProtection | None = None


def get_ssrf_protection() -> SSRFProtection:
    """Singleton getter for SSRFProtection."""
    global _global_ssrf_protection
    if _global_ssrf_protection is None:
        _global_ssrf_protection = SSRFProtection()
    return _global_ssrf_protection
