"""Built-in Chaos Engineering & Reliability Scenario Catalog."""

from dataclasses import dataclass, field
from typing import Any

from app.reliability.enums import FaultType, ScenarioCategory


@dataclass
class ScenarioDefinition:
    """Static definition of a built-in reliability / chaos scenario."""

    id: str
    name: str
    description: str
    category: ScenarioCategory
    severity: str
    fault_type: FaultType
    timeout_seconds: int = 60
    max_duration_seconds: int = 120
    parameters: dict[str, Any] = field(default_factory=dict)
    preconditions: list[str] = field(default_factory=list)
    expected_outcomes: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Complete Catalog of the 22 Minimum Required Scenarios (Section 44)
# -----------------------------------------------------------------------------

BUILTIN_SCENARIOS: list[ScenarioDefinition] = [
    # 1. PostgreSQL outage
    ScenarioDefinition(
        id="scen-pg-outage",
        name="PostgreSQL Outage & Connection Refusal",
        description="Simulate complete PostgreSQL unavailability. Proves API returns controlled 503, triggers SRE alert, and marks degraded state without raw exception exposure.",
        category=ScenarioCategory.DATABASE,
        severity="SEV1",
        fault_type=FaultType.POSTGRES_UNAVAILABLE,
        parameters={"duration_seconds": 15.0},
        preconditions=["PostgreSQL healthy"],
        expected_outcomes=["Controlled 503 error", "SRE alert fired", "Degraded operational state"],
    ),
    # 2. PostgreSQL latency
    ScenarioDefinition(
        id="scen-pg-latency",
        name="PostgreSQL Query Latency Spike",
        description="Inject 2000ms query latency into database operations. Proves query timeout safety and SLO latency breach detection.",
        category=ScenarioCategory.DATABASE,
        severity="SEV2",
        fault_type=FaultType.POSTGRES_LATENCY,
        parameters={"latency_ms": 2000.0, "duration_seconds": 15.0},
        preconditions=["PostgreSQL healthy"],
        expected_outcomes=[
            "P95 latency degradation",
            "SLO latency warning",
            "Timeout budget containment",
        ],
    ),
    # 3. Redis outage
    ScenarioDefinition(
        id="scen-redis-outage",
        name="Redis Outage & Cache Loss",
        description="Simulate Redis disconnection. Proves cache fail-open where permitted and fail-closed for critical locking without application crash.",
        category=ScenarioCategory.DEPENDENCY,
        severity="SEV2",
        fault_type=FaultType.REDIS_UNAVAILABLE,
        parameters={"duration_seconds": 15.0},
        preconditions=["Redis healthy"],
        expected_outcomes=["Graceful cache fallback", "SRE alert fired", "Dependency degraded"],
    ),
    # 4. Redis latency
    ScenarioDefinition(
        id="scen-redis-latency",
        name="Redis Cache Latency Degradation",
        description="Inject 1500ms latency into cache and lock calls. Verifies lock timeout and bounded request times.",
        category=ScenarioCategory.DEPENDENCY,
        severity="SEV3",
        fault_type=FaultType.REDIS_LATENCY,
        parameters={"latency_ms": 1500.0, "duration_seconds": 15.0},
        preconditions=["Redis healthy"],
        expected_outcomes=["Bounded cache timeout", "Operational state degraded"],
    ),
    # 5. Qdrant outage
    ScenarioDefinition(
        id="scen-qdrant-outage",
        name="Qdrant Vector Database Outage",
        description="Simulate vector search connection failure. Proves RAG and hybrid retrieval degrade to lexical/SQL search with 'insufficient evidence' warning.",
        category=ScenarioCategory.DEPENDENCY,
        severity="SEV2",
        fault_type=FaultType.QDRANT_UNAVAILABLE,
        parameters={"duration_seconds": 15.0},
        preconditions=["Qdrant healthy"],
        expected_outcomes=[
            "Controlled fallback to sparse search",
            "No unhandled 500 error",
            "Degraded mode active",
        ],
    ),
    # 6. Qdrant latency
    ScenarioDefinition(
        id="scen-qdrant-latency",
        name="Qdrant Search Latency Spike",
        description="Inject 3000ms latency on vector similarity search. Proves retrieval timeout budget is honored.",
        category=ScenarioCategory.DEPENDENCY,
        severity="SEV3",
        fault_type=FaultType.QDRANT_LATENCY,
        parameters={"latency_ms": 3000.0, "duration_seconds": 15.0},
        preconditions=["Qdrant healthy"],
        expected_outcomes=[
            "Vector search times out gracefully",
            "Parent orchestrator budget respected",
        ],
    ),
    # 7. LLM timeout
    ScenarioDefinition(
        id="scen-llm-timeout",
        name="LLM Provider Request Timeout",
        description="Simulate primary LLM provider hanging beyond gateway deadline. Proves circuit breaker and fallback trigger.",
        category=ScenarioCategory.LLM,
        severity="SEV2",
        fault_type=FaultType.LLM_TIMEOUT,
        parameters={"duration_seconds": 10.0},
        preconditions=["LLM Gateway healthy"],
        expected_outcomes=[
            "Gateway timeout detected",
            "Circuit breaker failure counted",
            "Fallback provider activated",
        ],
    ),
    # 8. LLM 5xx
    ScenarioDefinition(
        id="scen-llm-5xx",
        name="LLM Provider 502/503 Service Unavailable",
        description="Simulate upstream LLM HTTP 502/503 responses. Verifies retry policy with exponential backoff and max attempts.",
        category=ScenarioCategory.LLM,
        severity="SEV2",
        fault_type=FaultType.LLM_5XX,
        parameters={"error_code": 502, "duration_seconds": 10.0},
        preconditions=["LLM Gateway healthy"],
        expected_outcomes=[
            "Max 3 retries bounded",
            "Exponential backoff applied",
            "Fallback provider invoked",
        ],
    ),
    # 9. LLM 429
    ScenarioDefinition(
        id="scen-llm-429",
        name="LLM Provider 429 Rate Limit Spike",
        description="Simulate upstream rate limiting (HTTP 429). Verifies jittered backoff and immediate provider failover.",
        category=ScenarioCategory.LLM,
        severity="SEV2",
        fault_type=FaultType.LLM_429,
        parameters={"error_code": 429, "duration_seconds": 10.0},
        preconditions=["LLM Gateway healthy"],
        expected_outcomes=[
            "Rate limit recognized",
            "Circuit state increments",
            "Fast failover to backup tier",
        ],
    ),
    # 10. LLM malformed output
    ScenarioDefinition(
        id="scen-llm-malformed",
        name="LLM Provider Malformed JSON Response",
        description="Simulate invalid JSON or truncated structured output from LLM. Verifies schema parser rejection and controlled retry.",
        category=ScenarioCategory.LLM,
        severity="SEV3",
        fault_type=FaultType.LLM_MALFORMED,
        parameters={"duration_seconds": 10.0},
        preconditions=["LLM Gateway healthy"],
        expected_outcomes=[
            "Parsing validation error trapped",
            "Structured output repaired or rejected cleanly",
        ],
    ),
    # 11. LLM provider failover
    ScenarioDefinition(
        id="scen-llm-failover",
        name="LLM Multi-Provider Automated Failover",
        description="Simulate complete outage of Tier 1 model provider. Validates automatic transition to Tier 2 without losing request context.",
        category=ScenarioCategory.LLM,
        severity="SEV2",
        fault_type=FaultType.LLM_FAILOVER,
        parameters={"duration_seconds": 15.0},
        preconditions=["Primary and fallback providers configured"],
        expected_outcomes=[
            "Request succeeds via fallback",
            "Audit log records failover",
            "Alert noise contained",
        ],
    ),
    # 12. Worker crash
    ScenarioDefinition(
        id="scen-worker-crash",
        name="Worker Fleet Unexpected Crash During Ingestion",
        description="Simulate worker crash midway through document ingestion. Proves at-least-once lease visibility timeout and idempotent reprocessing.",
        category=ScenarioCategory.WORKER,
        severity="SEV2",
        fault_type=FaultType.WORKER_CRASH,
        parameters={"job_type": "ingestion", "duration_seconds": 15.0},
        preconditions=["Active background job executing"],
        expected_outcomes=[
            "No corrupted chunks",
            "Lease timeout expires",
            "Job reclaimed and completed",
        ],
    ),
    # 13. Queue backlog
    ScenarioDefinition(
        id="scen-queue-backlog",
        name="Background Queue Overload & Backpressure",
        description="Inject 500 rapid pending jobs. Proves worker saturation threshold, bounded queue memory, and queue lag alert.",
        category=ScenarioCategory.QUEUE,
        severity="SEV3",
        fault_type=FaultType.QUEUE_BACKLOG,
        parameters={"depth": 500, "duration_seconds": 20.0},
        preconditions=["Job queue operational"],
        expected_outcomes=[
            "Concurrency limit enforced",
            "Queue lag alert firing",
            "No out-of-memory crash",
        ],
    ),
    # 14. DLQ transition
    ScenarioDefinition(
        id="scen-dlq-transition",
        name="Poison Pill Job Dead Letter Queue (DLQ) Transition",
        description="Submit permanently failing job. Proves max retry exhaustion, DLQ placement, and audit notification without pipeline blockage.",
        category=ScenarioCategory.QUEUE,
        severity="SEV3",
        fault_type=FaultType.DLQ_TRANSITION,
        parameters={"max_retries": 3},
        preconditions=["DLQ enabled"],
        expected_outcomes=[
            "Job status FAILED",
            "Moved to DLQ",
            "Other queue items continue unblocked",
        ],
    ),
    # 15. SSE disconnect
    ScenarioDefinition(
        id="scen-sse-disconnect",
        name="Server-Sent Events (SSE) Abrupt Disconnect",
        description="Drop active client SSE stream during agent response. Proves server resource cleanup and buffer preservation.",
        category=ScenarioCategory.STREAMING,
        severity="SEV3",
        fault_type=FaultType.SSE_DISCONNECT,
        parameters={"duration_seconds": 10.0},
        preconditions=["Active SSE stream"],
        expected_outcomes=[
            "Server cleans up connection",
            "Replay buffer retains events",
            "No leaked coroutines",
        ],
    ),
    # 16. SSE reconnect
    ScenarioDefinition(
        id="scen-sse-reconnect",
        name="SSE Client Reconnection with Last-Event-ID",
        description="Reconnect client after brief drop using sequence ID. Verifies monotonic sequence, gapless replay, and deduplication.",
        category=ScenarioCategory.STREAMING,
        severity="SEV3",
        fault_type=FaultType.SSE_LATENCY,
        parameters={"replay_gap_events": 5},
        preconditions=["SSE connection interrupted"],
        expected_outcomes=[
            "Stream resumes from last event",
            "Zero duplicated events",
            "Monotonic ordering",
        ],
    ),
    # 17. API latency spike
    ScenarioDefinition(
        id="scen-api-latency",
        name="Platform API Global Latency Spike",
        description="Inject 1200ms synthetic latency across API router. Proves SRE SLI P95/P99 latency calculations and SLO breach generation.",
        category=ScenarioCategory.NETWORK,
        severity="SEV2",
        fault_type=FaultType.API_LATENCY,
        parameters={"latency_ms": 1200.0, "duration_seconds": 15.0},
        preconditions=["API serving requests"],
        expected_outcomes=["SLI latency rises", "SLO latency warning", "Error budget intact"],
    ),
    # 18. API error spike
    ScenarioDefinition(
        id="scen-api-error-spike",
        name="Platform API Synthetic 10% Error Spike",
        description="Inject controlled 10% error rate across endpoints. Proves Error Budget burn rate calculation, fast-burn alert, and SEV2 incident.",
        category=ScenarioCategory.NETWORK,
        severity="SEV2",
        fault_type=FaultType.API_ERROR_SPIKE,
        parameters={"error_rate": 0.10, "duration_seconds": 15.0},
        preconditions=["API healthy"],
        expected_outcomes=[
            "Error budget burns at >10x",
            "Burn-rate alert fires",
            "Incident created",
        ],
    ),
    # 19. Partial RAG failure
    ScenarioDefinition(
        id="scen-partial-rag",
        name="Partial Pipeline Failure: Vector Store Down, SQL Healthy",
        description="Simulate vector store failure while SQL database remains online. Proves orchestrator delivers partial response with grounding disclaimers.",
        category=ScenarioCategory.DEPENDENCY,
        severity="SEV3",
        fault_type=FaultType.QDRANT_UNAVAILABLE,
        parameters={"allow_partial": True},
        preconditions=["Orchestrator active"],
        expected_outcomes=[
            "SQL branch succeeds",
            "Vector branch reports degraded",
            "Grounded partial response",
        ],
    ),
    # 20. Tenant isolation under failure
    ScenarioDefinition(
        id="scen-tenant-isolation",
        name="Cross-Tenant Isolation Under Heavy Tenant A Failure",
        description="Inject 100% error rate and resource exhaustion strictly on Tenant A. Proves Tenant B requests, alerts, and data remain 100% healthy.",
        category=ScenarioCategory.SECURITY,
        severity="SEV1",
        fault_type=FaultType.API_ERROR_SPIKE,
        parameters={"target_tenant": "Tenant-A", "error_rate": 1.0},
        preconditions=["Two isolated tenants"],
        expected_outcomes=[
            "Tenant A degraded",
            "Tenant B 100% successful",
            "Zero cross-tenant data leakage",
        ],
    ),
    # 21. Recovery after dependency restoration
    ScenarioDefinition(
        id="scen-dependency-recovery",
        name="Full Automatic Recovery Following Dependency Restoration",
        description="Inject Redis outage, verify alert triggers, then restore Redis. Proves automated recovery, alert resolution, and health matrix return to green.",
        category=ScenarioCategory.RECOVERY,
        severity="SEV2",
        fault_type=FaultType.REDIS_UNAVAILABLE,
        parameters={"duration_seconds": 10.0},
        preconditions=["Redis outage injected"],
        expected_outcomes=[
            "Dependency restored",
            "Alert status RESOLVED",
            "Operational status HEALTHY",
        ],
    ),
    # 22. Release gate after SLO degradation
    ScenarioDefinition(
        id="scen-release-gate-block",
        name="Production Release Gate Blockade Under Exhausted Budget",
        description="Inject sustained error spike that exhausts error budget. Proves Release Safety Gate automatically returns BLOCK.",
        category=ScenarioCategory.SECURITY,
        severity="SEV1",
        fault_type=FaultType.API_ERROR_SPIKE,
        parameters={"error_rate": 0.50, "duration_seconds": 20.0},
        preconditions=["Release gate configured"],
        expected_outcomes=[
            "Error budget depleted",
            "Release gate verdict BLOCK",
            "Deployments prohibited",
        ],
    ),
]


class ScenarioRegistry:
    """Registry maintaining both built-in and tenant-defined chaos scenarios."""

    def __init__(self) -> None:
        self._scenarios: dict[str, ScenarioDefinition] = {s.id: s for s in BUILTIN_SCENARIOS}

    def get(self, scenario_id: str) -> ScenarioDefinition | None:
        return self._scenarios.get(scenario_id)

    def list_all(self, category: ScenarioCategory | None = None) -> list[ScenarioDefinition]:
        if category is None:
            return list(self._scenarios.values())
        return [s for s in self._scenarios.values() if s.category == category]

    def register(self, scenario: ScenarioDefinition) -> None:
        self._scenarios[scenario.id] = scenario


GLOBAL_SCENARIO_REGISTRY = ScenarioRegistry()
