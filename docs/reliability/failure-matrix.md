# Failure Injection Matrix & Scenario Catalog

The platform implements 22 pre-configured, deterministic chaos scenarios categorized into 10 failure domains.

| Scenario ID | Category | Fault Type | Severity | Description | Invariant Assertions |
|-------------|----------|------------|----------|-------------|----------------------|
| `sc-db-01` | DATABASE | POSTGRES_UNAVAILABLE | SEV1 | Primary database becomes completely unreachable. | NO_FAIL_OPEN, CIRCUIT_BREAKER, RECOVERY_SUCCESS |
| `sc-db-02` | DATABASE | POSTGRES_LATENCY | SEV2 | Queries experience 2500ms injected latency. | TIMEOUT_BUDGET, DEGRADATION |
| `sc-db-03` | DATABASE | POSTGRES_UNAVAILABLE | SEV1 | Database connection pool is fully exhausted. | RETRY_BOUNDS, NO_LEAK |
| `sc-db-04` | DATABASE | POSTGRES_LATENCY | SEV2 | Partial transaction failure during analysis pipeline. | DATA_INTEGRITY, TRANSACTION_ROLLBACK |
| `sc-net-01` | NETWORK | REDIS_UNAVAILABLE | SEV2 | Redis cache & session store unavailable. | DEGRADATION, NO_FAIL_OPEN, RECOVERY_SUCCESS |
| `sc-net-02` | NETWORK | REDIS_LATENCY | SEV3 | Redis experiences 1500ms network roundtrip delay. | TIMEOUT_BUDGET, CIRCUIT_BREAKER |
| `sc-dep-01` | DEPENDENCY | QDRANT_UNAVAILABLE | SEV2 | Qdrant vector database unreachable for semantic search. | DEGRADATION, NO_CRASH |
| `sc-dep-02` | DEPENDENCY | QDRANT_LATENCY | SEV3 | Qdrant search queries exceed normal timeout. | TIMEOUT_BUDGET, FALLBACK |
| `sc-llm-01` | LLM | LLM_429 | SEV2 | Primary LLM returns HTTP 429 Too Many Requests. | RETRY_BOUNDS, EXPONENTIAL_BACKOFF |
| `sc-llm-02` | LLM | LLM_5XX | SEV1 | Primary LLM returns HTTP 500 Internal Server Error. | FAILOVER, CIRCUIT_BREAKER |
| `sc-llm-03` | LLM | LLM_TIMEOUT | SEV2 | LLM gateway request exceeds client deadline. | TIMEOUT_BUDGET, CANCELLATION |
| `sc-llm-04` | LLM | LLM_MALFORMED | SEV2 | LLM returns non-JSON or invalid schema payload. | SCHEMA_VALIDATION, DEGRADATION |
| `sc-llm-05` | LLM | LLM_FAILOVER | SEV2 | Primary model fails repeatedly; trigger secondary model. | FAILOVER_SUCCESS, AUDIT_TRAIL |
| `sc-wrk-01` | WORKER | WORKER_CRASH | SEV1 | Celery worker killed by SIGKILL mid-task execution. | TASK_REQUEUE, DATA_INTEGRITY |
| `sc-wrk-02` | WORKER | QUEUE_BACKLOG | SEV2 | Task backlog grows to 10,000 pending items. | RETRY_BOUNDS, LAG_ALERT |
| `sc-wrk-03` | WORKER | DLQ_TRANSITION | SEV2 | Poison pill task exceeds maximum retry attempts. | DLQ_ROUTING, RECOVERY_SUCCESS |
| `sc-sse-01` | STREAMING | SSE_DISCONNECT | SEV2 | Client socket terminated abruptly mid-token generation. | RECONNECT_RESUME, ZERO_ORPHAN |
| `sc-sse-02` | STREAMING | SSE_LATENCY | SEV3 | Network buffer introduces 800ms jitter between SSE frames. | BACKPRESSURE, INTEGRITY |
| `sc-sec-01` | SECURITY | POSTGRES_UNAVAILABLE | SEV1 | Database degraded; verify tenant isolation barrier holds. | TENANT_ISOLATION, NO_LEAK |
| `sc-sec-02` | SECURITY | REDIS_UNAVAILABLE | SEV1 | Session store down; verify auth barrier rejects invalid tokens. | NO_FAIL_OPEN, SECURITY_BARRIER |
| `sc-res-01` | RESOURCE | API_ERROR_SPIKE | SEV2 | Sudden 50x request spike triggers circuit breaker. | CIRCUIT_BREAKER, BOUNDED_RETRY |
| `sc-rec-01` | RECOVERY | POSTGRES_UNAVAILABLE | SEV1 | Outage resolved; verify full auto-reconnection and cache warmup. | RECOVERY_SUCCESS, DATA_INTEGRITY |

---

## Invariant Assertion Rules

1. **DATA_INTEGRITY**: Database state post-scenario matches expectation; rollback verified on uncommitted operations.
2. **TENANT_ISOLATION**: Query results contain exclusively the requesting tenant's `organization_id`. Cross-tenant penetration attempts must return HTTP 403 or empty sets.
3. **NO_FAIL_OPEN**: When security policies or auth stores fail, access is denied by default.
4. **RETRY_BOUNDS**: System attempts no more than configured retry limit (default: 3 attempts) with jittered backoff.
5. **CIRCUIT_BREAKER**: Tripped after consecutive failure threshold; resets to HALF_OPEN after cooldown.
6. **TIMEOUT_BUDGET**: Subsystems yield within specified timeout budgets without hanging parent processes.
7. **RECOVERY_SUCCESS**: All subsystems transition back to `HEALTHY` within MTTR threshold.
