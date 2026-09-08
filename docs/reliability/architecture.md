# Enterprise Reliability & Chaos Engineering Architecture

## 1. Overview & Objectives

The Production Reliability and Chaos Engineering framework provides empirical, measurable verification that the Enterprise AI Analyst platform withstands severe operational degradation, dependency failure, and network latency without violating core safety invariants.

The framework bridges the gap between static unit tests and dynamic production readiness by injecting controlled, bounded, and deterministic faults into subsystems and validating:
1. **Fault Containment**: Failures are isolated to their originating domain without cascading into catastrophic cluster failures.
2. **Deterministic Invariant Preservation**: Zero tenant data leakage, zero silent data corruption, and strict security barrier enforcement (no fail-open).
3. **Automated Recovery & Observability**: Degradations are automatically detected (MTTD), attributed (MTTA), and resolved (MTTR), emitting SRE alerts and recording incident records.

---

## 2. Core Architectural Components

The reliability architecture lives within `backend/app/reliability/` and consists of 8 primary layers:

```mermaid
graph TD
    API[REST API /api/v1/reliability] --> Service[ReliabilityService]
    Service --> Registry[ScenarioRegistry (22 Scenarios)]
    Service --> FaultEngine[FaultContext & Injectors]
    Service --> AssertionEngine[ReliabilityAssertionEngine]
    Service --> RecoveryTimeline[RecoveryTimeline & Validator]
    Service --> ScoringEngine[ReliabilityScoringEngine]
    Service --> ReadinessEngine[ProductionReadinessEvaluator]
    Service --> Repo[ReliabilityRepository (PostgreSQL)]
    
    FaultEngine --> ExtDB[(PostgreSQL / Redis / Qdrant)]
    FaultEngine --> LLMGateway[LLM Gateway / Circuit Breaker]
    FaultEngine --> Workers[Celery / Task Workers]
    FaultEngine --> SSE[SSE / Streaming Transports]
```

### 2.1 Fault Injection Framework (`faults.py`, `injectors.py`)
- **Isolation Guarantee**: Faults are applied only to scoped operations via `FaultContext` and context managers.
- **Safety Boundaries**: Strictly disallows execution if `ENVIRONMENT == 'production'`.
- **Guaranteed Reversibility**: Built with explicit `finally: recover_fault()` hooks to ensure no persistent corruption or orphaned mock state.
- **Injectors**:
  - `DatabaseFaultInjector`: Latency injection, pool exhaustion, forced connectivity disconnection.
  - `RedisFaultInjector`: Cache outage, lock acquisition timeout, pub/sub drop.
  - `QdrantFaultInjector`: Vector search timeout, index unavailability.
  - `LLMFaultInjector`: Rate limiting (429), provider 5xx, token timeout, malformed JSON response, failover triggering.
  - `WorkerFaultInjector`: Worker process crash, task queue backlog buildup, DLQ transition.
  - `SSEFaultInjector`: Connection disconnect mid-stream, frame delivery delay.
  - `APIFaultInjector`: Upstream latency, synthetic error spikes.

### 2.2 Scenario Registry (`scenarios.py`)
Houses 22 deterministic scenarios across 10 functional categories:
- `DATABASE`: Connection drops, connection pool exhaustion, transaction rollback under failure.
- `NETWORK` / `DEPENDENCY`: Redis unavailability, Qdrant vector timeout.
- `LLM`: Rate limit backoff (429), provider outage failover, token timeout budget, malformed structured output.
- `WORKER`: Crash during execution, task queue lag recovery, DLQ transition.
- `STREAMING`: SSE disconnect with stateful resume, mid-stream event backpressure.
- `SECURITY`: Tenant isolation under database failure, auth failure barrier (no fail-open).
- `RESOURCE`: Circuit breaker trip and cooldown, burst traffic retry storm bounding.
- `RECOVERY`: Self-healing after outage, cache warm-up post-recovery.

### 2.3 Invariant Assertions Engine (`assertions.py`)
Evaluates strict operational criteria on every run:
- `DATA_INTEGRITY`: Zero orphaned records, consistent transaction boundaries.
- `TENANT_ISOLATION`: Strict cross-tenant query suppression even when metadata caches fail.
- `NO_FAIL_OPEN`: Auth and permission gates always default to Deny on subsystem exceptions.
- `RETRY_BOUNDS`: Exponential backoff with jitter, avoiding thundering herds.
- `CIRCUIT_BREAKER`: Breaker state transitions from CLOSED -> OPEN -> HALF_OPEN without unhandled crashes.
- `TIMEOUT_BUDGET`: Client requests honor upstream cancellation boundaries without hanging workers.
- `RECOVERY_SUCCESS`: Subsystem health returns to 100% operational baseline post-injection.

### 2.4 Recovery Timeline Engine (`recovery.py`)
Calculates empirical reliability metrics for each chaos run:
- **MTTD (Mean Time to Detect)**: Duration between fault injection and initial monitoring detection.
- **MTTA (Mean Time to Acknowledge)**: Duration until automated alerting or SRE incident creation.
- **MTTR (Mean Time to Recover)**: Duration from fault resolution until verification assertions pass.
- **Time to Recovery**: Total elapsed wall-clock duration of the degradation episode.

### 2.5 Reliability Scoring & Production Readiness (`scoring.py`, `readiness.py`)
- **Scorecard Engine**: Calculates weighted composite scores (0–100) across 6 dimensions:
  - Detection Score (15%)
  - Recovery Score (25%)
  - Data Integrity Score (25%)
  - Graceful Degradation Score (15%)
  - Tenant Isolation Score (10%)
  - SLO Impact Score (10%)
- **Production Readiness Evaluator**:
  - Compiles test suite results, security audits, backup verification, and chaos scenario pass rates.
  - Generates an authoritative verdict: `READY`, `READY_WITH_WARNINGS`, or `NOT_READY`.
  - Enforces hard blockers: Any tenant isolation failure, auth fail-open, or uncontained data corruption automatically produces `NOT_READY`.
