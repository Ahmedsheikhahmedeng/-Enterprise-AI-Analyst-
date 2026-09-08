"""Alert routing and notification provider abstractions."""

from abc import ABC, abstractmethod
from typing import Any


class NotificationProvider(ABC):
    """Abstract interface for operational alerting notification channels."""

    @abstractmethod
    async def send_notification(self, alert_payload: dict[str, Any]) -> bool:
        """Deliver alert notification. Returns True if successfully accepted."""
        pass


class InAppNotificationProvider(NotificationProvider):
    """Production in-app notification provider recording notifications locally."""

    def __init__(self) -> None:
        self.delivered_records: list[dict[str, Any]] = []

    async def send_notification(self, alert_payload: dict[str, Any]) -> bool:
        """Record notification in internal ledger."""
        self.delivered_records.append(alert_payload)
        return True


def match_routing_rule(
    rule_service: str | None,
    rule_severity: str | None,
    rule_environment: str | None,
    alert_service: str,
    alert_severity: str,
    current_environment: str = "production",
) -> bool:
    """Evaluate whether an alert matches a routing rule."""
    if rule_service and rule_service.lower() != alert_service.lower():
        return False
    if rule_severity and rule_severity.upper() != alert_severity.upper():
        return False
    return not (rule_environment and rule_environment.lower() != current_environment.lower())
