# Reliability Testing & Test Suite Guide

## 1. Test Suite Architecture

The reliability test suite is housed under `backend/tests/reliability/` and provides comprehensive verification of the chaos engine, fault injectors, invariants, and SRE integration:

| Test File | Focus | Scenarios / Assertions Tested |
|-----------|-------|-------------------------------|
| `test_scenarios.py` | Catalog validation | Confirms all 22 scenarios exist, have valid categories, timeouts, and required parameters. |
| `test_fault_injection.py` | Injectors & Guards | Verifies Database, Redis, Qdrant, LLM, Worker, SSE, and API fault injection and reversibility. Also validates environmental production safety guard. |
| `test_recovery.py` | Recovery metrics | Verifies MTTD, MTTA, MTTR, and total time to recovery calculations. |
| `test_slo_impact.py` | SRE integration | Tests SLO degradation and error budget consumption calculations. |
| `test_dependencies.py` | External dependencies | Simulates Redis and Qdrant unavailability and verifies graceful fallback. |
| `test_worker_recovery.py` | Async task workers | Tests Celery worker crash recovery and dead-letter queue routing. |
| `test_llm_failover.py` | LLM Gateway resilience | Tests 429 rate limit backoff, 5xx failover to secondary provider, and circuit breaker trip. |
| `test_sse_failure.py` | Streaming reliability | Tests client mid-stream disconnect and network latency buffering. |
| `test_tenant_isolation.py` | Multi-tenancy under stress | Asserts that cross-tenant access is strictly blocked during database latency and failure. |
| `test_security_under_failure.py`| Security barriers | Validates no fail-open behavior when auth caches or token verifiers fail. |
| `test_integrity.py` | Data consistency | Validates database transaction rollback on partial execution failure. |
| `test_readiness.py` | Production readiness | Tests evaluator scoring, warning generation, and hard blocker triggers. |
| `test_chaos_pipeline.py` | End-to-end flow | Runs scenario execution pipeline, persistence, and scorecard generation. |

---

## 2. Running Reliability Tests

### Run Dedicated Reliability Suite
```bash
pytest backend/tests/reliability/ -v
```

### Run Multi-Tenancy & Security Verification Only
```bash
pytest backend/tests/reliability/test_tenant_isolation.py backend/tests/reliability/test_security_under_failure.py -v
```

### Run Full System Regression
```bash
pytest backend/tests/ -q
```
