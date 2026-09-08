# SRE Operational Troubleshooting Guide

## 1. Fast Diagnostic Workflow

When responding to an operational alert or declaring an incident:

1. **Check Operational Status**:
   ```bash
   curl -s http://localhost:8000/api/v1/sre/dashboards/overview
   ```
2. **Inspect Backing Dependencies**:
   ```bash
   curl -s http://localhost:8000/api/v1/sre/dependencies
   ```
3. **List Active Firing Alerts**:
   ```bash
   curl -s http://localhost:8000/api/v1/sre/alerts?status=FIRING
   ```
4. **Locate Associated Runbook**:
   Inspect `/api/v1/sre/runbooks` for non-destructive diagnostic steps matching the active symptom.

---

## 2. Common Failure Modes & Safe Diagnostic Actions

### PostgreSQL Connection Pool Exhaustion
* **Symptom**: `Asyncpg PoolTimeout` or latency spikes on read endpoints.
* **Safe Check**: Verify count of active transactions in `pg_stat_activity`.
* **Prohibited**: Do NOT execute `kill -9` on database server processes or drop tables.

### Worker Task Queue Lag Spikes
* **Symptom**: Delayed async analysis execution or background batch processing backlog.
* **Safe Check**: Inspect Redis queue length and dead-letter message store.
* **Safe Action**: Scale background worker instances within configured limits.

### LLM Gateway Rate-Limit / Failover
* **Symptom**: Upstream provider 429 errors.
* **Safe Action**: Verify that automatic fallback provider routing is engaged in the gateway settings.
