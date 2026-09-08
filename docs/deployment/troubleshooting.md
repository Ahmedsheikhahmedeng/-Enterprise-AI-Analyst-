# Production Operations & Troubleshooting Runbook

## 1. Backing Infrastructure Incidents

### A. PostgreSQL Unavailable
- **Symptom**: `GET /api/v1/platform/ready` returns `503 Service Unavailable`, logs report connection timeouts.
- **Triage**:
  ```bash
  docker logs analyst_prod_postgres --tail 100
  docker exec analyst_prod_postgres pg_isready -U analyst_prod_user
  ```
- **Mitigation**: Check disk space on persistent volume `analyst_prod_postgres_data`. If restarted, verify connection pool recovery via `GET /api/v1/platform/ready`.

### B. Redis Unavailable
- **Symptom**: Rate limiting fails open or blocks; asynchronous job queues stall; SSE heartbeat disconnects.
- **Triage**:
  ```bash
  docker logs analyst_prod_redis --tail 100
  docker exec analyst_prod_redis redis-cli -a <password> ping
  ```
- **Mitigation**: Check Redis memory allocation (`maxmemory 768mb`). Ensure memory policy `allkeys-lru` is evicting transient caches.

### C. Qdrant Vector Engine Unavailable
- **Symptom**: Vector retrieval and Hybrid RAG queries fail; Text-to-SQL operates in degraded mode.
- **Graceful Degradation**: Direct SQL agent continues functioning; platform returns partial answers if semantic search is disabled.
- **Triage**:
  ```bash
  docker logs analyst_prod_qdrant --tail 100
  curl -I http://localhost:6333/healthz
  ```

### D. Worker Process Unavailable / Crash
- **Symptom**: Jobs remain in `QUEUED` state without transitioning to `RUNNING`.
- **Triage**:
  ```bash
  docker logs analyst_prod_worker --tail 100
  ```
- **Graceful Shutdown**: On restart or SIGTERM, workers release job leases within 30s.

### E. Real-Time SSE Connection Drops
- **Symptom**: Frontend reconnects continuously or misses event sequence chunks.
- **Mitigation**:
  1. Ensure reverse proxy (Nginx) has `proxy_buffering off;` and `proxy_read_timeout 3600s;`.
  2. Verify that client requests missing chunks using `GET /api/v1/ask/{id}/events?after_sequence=N`.

### F. LLM Provider Outage
- **Symptom**: `504 Gateway Timeout` or `502 Bad Gateway` on `/api/v1/ask`.
- **Mitigation**: Automatic retries execute with exponential backoff. Fallback models activate if secondary providers are configured.
