# Chaos Engineering Methodology & Safety Controls

## 1. Principles of Chaos Engineering

Chaos engineering at the enterprise level is not about breaking systems unpredictably in production; it is about empirical hypothesis testing in controlled environments.

Our implementation follows 5 core tenets:
1. **Hypothesize Steady State**: Define expected behavior (e.g. "API latencies remain <= 500ms p95; errors gracefully degrade to 503 without leaking tenant data").
2. **Inject Real-World Variables**: Simulate realistic failures: network packet loss, slow queries, worker kills, rate limits.
3. **Automate Invariant Verification**: Run programmatic assertions directly against database states, auth contexts, and response payloads.
4. **Minimize Blast Radius**: Every chaos experiment is executed within a dedicated execution context, with bounded duration and auto-rollback.
5. **Strict Safety Gates**: Prohibit live execution against production clusters without pre-approved maintenance windows and explicit manual override.

---

## 2. Safety Architecture & Safeguards

```
[Trigger Run] 
      │
      ▼
[Environment Check] ──(env == 'production')──> [ABORT / HTTP 403 Security Violation]
      │
      ▼ (env in {'test', 'staging', 'development'})
[FaultContext Setup] ──> [Inject Fault (bounded duration / max_duration)]
      │
      ▼
   [Execute Scenario Payload]
      │
      ▼
   [FINALLY Block Guarantee] ──> [Revert Faults / Restore Connections / Clear Mocks]
      │
      ▼
[Evaluate Invariant Assertions] ──> [Persist Run & Scorecard]
```

### 2.1 Environmental Guards
- In `backend/app/reliability/faults.py` and `service.py`, every execution path verifies:
  ```python
  if environment == "production":
      raise SafetyViolationError("Chaos experiments strictly prohibited in production")
  ```
- Frontend UI disables the 'Production' option by default with a safety tooltip.

### 2.2 Reversibility & Cleanup
Every fault injector implements the `recover()` hook. In `FaultContext`:
```python
async with FaultContext(fault_config) as ctx:
    # scenario runs here
# ctx.__aexit__ automatically calls injector.recover()
```
Even if an unhandled assertion or timeout occurs, Python `async with` guarantees complete teardown.

---

## 3. Running Chaos Scenarios

### Via API
```bash
POST /api/v1/reliability/runs
Content-Type: application/json
Authorization: Bearer <ADMIN_OR_OPERATOR_TOKEN>

{
  "scenario_id": "sc-llm-01",
  "environment": "test",
  "dry_run": false
}
```

### Via CLI / Test Automation
```bash
pytest backend/tests/reliability/test_scenarios.py -k "test_llm_provider_outage"
```

### Expected Output
The system responds with a complete `ReliabilityRun` containing:
- Injected faults and their exact lifecycle timestamps.
- Evaluated assertions (`PASSED`, `FAILED`, `WARNING`).
- Calculated MTTD, MTTA, MTTR.
- SRE integration details (alerts fired, incidents logged, error budget burned).
