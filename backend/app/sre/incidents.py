"""Enterprise Incident Lifecycle FSM, event timeline logging, MTTA, and MTTR calculation."""

import statistics
from collections.abc import Sequence
from datetime import datetime

from app.sre.enums import IncidentStatusEnum

# Explicit legal state transition map
ALLOWED_TRANSITIONS: dict[IncidentStatusEnum, set[IncidentStatusEnum]] = {
    IncidentStatusEnum.OPEN: {
        IncidentStatusEnum.ACKNOWLEDGED,
        IncidentStatusEnum.INVESTIGATING,
        IncidentStatusEnum.RESOLVED,  # Fast resolution allowed for trivial events
    },
    IncidentStatusEnum.ACKNOWLEDGED: {
        IncidentStatusEnum.INVESTIGATING,
        IncidentStatusEnum.MITIGATED,
        IncidentStatusEnum.RESOLVED,
    },
    IncidentStatusEnum.INVESTIGATING: {
        IncidentStatusEnum.MITIGATED,
        IncidentStatusEnum.RESOLVED,
    },
    IncidentStatusEnum.MITIGATED: {
        IncidentStatusEnum.INVESTIGATING,  # If mitigation fails, back to investigation
        IncidentStatusEnum.RESOLVED,
    },
    IncidentStatusEnum.RESOLVED: {
        IncidentStatusEnum.CLOSED,
    },
    IncidentStatusEnum.CLOSED: set(),  # Terminal state: no further transitions permitted
}


class InvalidIncidentTransitionError(Exception):
    """Raised when an illegal incident lifecycle state transition is requested."""

    def __init__(self, current_status: str, target_status: str):
        super().__init__(
            f"Illegal incident transition from '{current_status}' to '{target_status}'. "
            f"Terminal or backward transitions are forbidden by SRE policy."
        )
        self.current_status = current_status
        self.target_status = target_status


def validate_incident_transition(
    current_status: IncidentStatusEnum | str,
    target_status: IncidentStatusEnum | str,
) -> None:
    """Validate that moving from current_status to target_status follows the SRE FSM."""
    curr = IncidentStatusEnum(current_status)
    target = IncidentStatusEnum(target_status)

    if curr == target:
        return

    allowed = ALLOWED_TRANSITIONS.get(curr, set())
    if target not in allowed:
        raise InvalidIncidentTransitionError(curr.value, target.value)


def calculate_mtta_seconds(opened_at: datetime, acknowledged_at: datetime | None) -> float | None:
    """Calculate Mean Time To Acknowledge in seconds."""
    if not acknowledged_at or acknowledged_at < opened_at:
        return None
    return (acknowledged_at - opened_at).total_seconds()


def calculate_mttr_seconds(opened_at: datetime, resolved_at: datetime | None) -> float | None:
    """Calculate Mean Time To Resolve in seconds."""
    if not resolved_at or resolved_at < opened_at:
        return None
    return (resolved_at - opened_at).total_seconds()


def aggregate_mttr_metrics(
    durations_seconds: Sequence[float],
) -> dict[str, float | None]:
    """Calculate average, median, and p95 MTTR from historical durations."""
    valid_durations = [d for d in durations_seconds if d is not None and d >= 0.0]
    if not valid_durations:
        return {"average": None, "median": None, "p95": None}

    avg = statistics.mean(valid_durations)
    med = statistics.median(valid_durations)

    # p95 calculation
    sorted_d = sorted(valid_durations)
    idx = int(0.95 * len(sorted_d))
    idx = min(idx, len(sorted_d) - 1)
    p95 = sorted_d[idx]

    return {
        "average": round(avg, 2),
        "median": round(med, 2),
        "p95": round(p95, 2),
    }
