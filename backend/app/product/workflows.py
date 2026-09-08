"""Cross-cutting workflow state machine validators and integrity audits."""

from pydantic import BaseModel, Field


class StateMachineValidationResult(BaseModel):
    domain: str
    is_valid: bool
    allowed_transitions: int
    unreachable_states: list[str] = Field(default_factory=list)
    dead_end_states: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)


class WorkflowAuditSummary(BaseModel):
    total_domains_audited: int
    all_valid: bool
    domains: dict[str, StateMachineValidationResult] = Field(default_factory=dict)


class WorkflowStateMachineAuditor:
    """Audits state machines across all subsystems to prevent illegal, corrupted, or impossible states."""

    STATE_MACHINES: dict[str, dict[str, set[str]]] = {
        "agent_session": {
            "CREATED": {"PLANNING", "CANCELLED", "FAILED"},
            "PLANNING": {"EXECUTING", "AWAITING_APPROVAL", "FAILED"},
            "EXECUTING": {"AWAITING_APPROVAL", "CHECKPOINTED", "COMPLETED", "FAILED", "CANCELLED"},
            "AWAITING_APPROVAL": {"EXECUTING", "REJECTED", "CANCELLED", "FAILED"},
            "CHECKPOINTED": {"EXECUTING", "CANCELLED"},
            "COMPLETED": set(),  # Terminal
            "REJECTED": set(),  # Terminal
            "CANCELLED": set(),  # Terminal
            "FAILED": set(),  # Terminal
        },
        "background_job": {
            "QUEUED": {"RUNNING", "CANCELLED"},
            "RUNNING": {"COMPLETED", "FAILED", "RETRYING"},
            "RETRYING": {"RUNNING", "FAILED"},
            "COMPLETED": set(),
            "FAILED": set(),
            "CANCELLED": set(),
        },
        "sre_incident": {
            "DETECTED": {"INVESTIGATING"},
            "INVESTIGATING": {"MITIGATING", "RESOLVED"},
            "MITIGATING": {"RESOLVED", "INVESTIGATING"},
            "RESOLVED": {"POSTMORTEM", "CLOSED"},
            "POSTMORTEM": {"CLOSED"},
            "CLOSED": set(),
        },
        "governance_approval": {
            "PENDING": {"APPROVED", "REJECTED", "EXPIRED"},
            "APPROVED": {"EXECUTED", "FAILED"},
            "REJECTED": set(),
            "EXPIRED": set(),
            "EXECUTED": set(),
            "FAILED": set(),
        },
        "finops_budget": {
            "HEALTHY": {"WARNING", "CRITICAL", "EXCEEDED"},
            "WARNING": {"HEALTHY", "CRITICAL", "EXCEEDED"},
            "CRITICAL": {"WARNING", "EXCEEDED", "HEALTHY"},
            "EXCEEDED": {"HEALTHY"},  # When new budget period begins or limit raised
        },
    }

    @classmethod
    def audit_domain(cls, domain: str) -> StateMachineValidationResult:
        if domain not in cls.STATE_MACHINES:
            return StateMachineValidationResult(
                domain=domain,
                is_valid=False,
                allowed_transitions=0,
                violations=[f"Domain '{domain}' not defined in registered state machines."],
            )

        fsm = cls.STATE_MACHINES[domain]
        all_states = set(fsm.keys())
        target_states = {t for targets in fsm.values() for t in targets}
        transitions_count = sum(len(targets) for targets in fsm.values())

        violations: list[str] = []

        # Check unknown target states
        for src, targets in fsm.items():
            for tgt in targets:
                if tgt not in all_states:
                    violations.append(f"State '{src}' transitions to unknown state '{tgt}'.")

        # Initial states are typically those with keys
        unreachable = [s for s in all_states if s not in target_states and s != list(all_states)[0]]

        return StateMachineValidationResult(
            domain=domain,
            is_valid=len(violations) == 0,
            allowed_transitions=transitions_count,
            unreachable_states=unreachable,
            dead_end_states=[s for s, t in fsm.items() if len(t) == 0],
            violations=violations,
        )

    @classmethod
    def audit_all(cls) -> WorkflowAuditSummary:
        results = {domain: cls.audit_domain(domain) for domain in cls.STATE_MACHINES}
        all_valid = all(r.is_valid for r in results.values())
        return WorkflowAuditSummary(
            total_domains_audited=len(results),
            all_valid=all_valid,
            domains=results,
        )

    @classmethod
    def validate_transition(cls, domain: str, current_state: str, new_state: str) -> bool:
        fsm = cls.STATE_MACHINES.get(domain)
        if not fsm:
            return False
        allowed = fsm.get(current_state, set())
        return new_state in allowed
