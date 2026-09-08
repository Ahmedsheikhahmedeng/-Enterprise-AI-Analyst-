# TASK 21 — Production Observability, Distributed Tracing & Monitoring

## 1. Architecture Overview

Task 21 establishes an enterprise-grade observability, telemetry, and monitoring layer designed specifically for high-reliability AI platforms. It provides full runtime visibility across HTTP endpoints, deterministic planning, Text-to-SQL generation, hybrid RAG retrieval, and LLM inference while maintaining strict multi-tenant boundaries and preventing secret or high-cardinality leakage.

```
Incoming Request (HTTP / REST)
       │
       ▼
[ObservabilityMiddleware] ──► Injects Request/Trace IDs & W3C traceparent (00-trace-span-01)
       │                  ──► Binds immutable ObservabilityContext via ContextVars
       │                  ──► Tracks in-flight gauge & records duration histogram
       ▼
[AIAnalystService / API Router]
       │
       ├──► [analyst.ask span]
       │        ├── [analyst.plan span]
       │        ├── [analyst.sql span] ──► [sql.schema / validation / execution / analysis]
       │        ├── [analyst.rag span] ──► [retrieval.hybrid / reranking / generation]
       │        ├── [analyst.merge span]
       │        ├── [analyst.conflict_detection span]
       │        └── [analyst.final_generation span]
       │
       ▼
[TelemetryRedactor] ───────► Central sanitization of Bearer tokens, DB DSN passwords, API keys
       │
       ▼
[MetricsRegistry] ─────────► Thread-safe Counters, Gauges, and Histograms
       │                  ──► Forbidden label validation (HighCardinalityViolationError)
       │
       ├──► [LoggingExporter] ────► Structured JSON logs
       ├──► [PrometheusExporter] ─► OpenMetrics / Prometheus exposition (/api/v1/observability/metrics)
       └──► [OpenTelemetryExporter]► OTel ResourceMetrics schema
```

---

## 2. Core Observability Context & Propagation

The `ObservabilityContext` is an immutable frozen dataclass that carries correlation across execution boundaries without relying on mutable global variables:

```python
@dataclass(frozen=True)
class ObservabilityContext:
    request_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    organization_id: UUID | None = None
    user_id: UUID | None = None
    route: str | None = None
    http_method: str | None = None
    started_at: datetime = datetime.now(UTC)
    is_sampled: bool = True
```

Async execution boundaries manage context using Python's `contextvars.ContextVar`, ensuring each concurrent request maintains an isolated trace state:
- Root context is bound on incoming HTTP dispatch.
- Child spans derive from parent contexts using `ctx.with_span(new_span_id=...)`.
- Correlating headers `X-Request-ID`, `X-Trace-ID`, and `traceparent` (W3C standard format: `00-{trace_id}-{span_id}-{flags}`) are returned on all HTTP responses.

---

## 3. Distributed Tracing & Span Nesting

The `TraceManager` handles the lifecycle of synchronous and asynchronous spans:
- `start_span_async(name, kind, attributes)`
- `start_span_sync(name, kind, attributes)`

Spans record:
- `span_id`, `trace_id`, `parent_span_id`
- `name` (e.g. `analyst.ask`, `analyst.plan`, `analyst.sql`, `analyst.rag`)
- `kind` (`INTERNAL`, `SERVER`, `CLIENT`)
- `start_time`, `end_time`, `duration_ms`
- `status` (`OK`, `ERROR`)
- `attributes` (automatically sanitized through `TelemetryRedactor`)

When an exception occurs within a span, the status is set to `ERROR`, the exception type is captured, and the error message is sanitized before recording.

---

## 4. Centralized Redaction Layer (`TelemetryRedactor`)

Telemetry must never become an exfiltration channel for credentials or confidential data. The `TelemetryRedactor` centrally applies regex patterns and recursive dictionary sanitization:
- **Authorization Bearer Tokens**: Replaces raw JWTs with `Bearer [REDACTED]`.
- **Database DSN Passwords**: Replaces `postgresql://user:secret@host/db` with `postgresql://user:[REDACTED]@host/db`.
- **API Keys & Secrets**: Inspects keys containing `api_key`, `secret`, `token`, `password`, `private_key` and redacts values to `[REDACTED]`.
- **High-Risk Headers**: Sanitizes headers and payload dictionaries prior to metrics aggregation or trace recording.

---

## 5. Metrics Registry & Cardinality Protection

The `MetricsRegistry` supports thread-safe monotonic `Counter`, point-in-time `Gauge`, and bucketed `Histogram` instruments.

### High-Cardinality Protection
Metric label cardinality is strictly guarded against explosion:
```python
FORBIDDEN_LABEL_KEYS: frozenset[str] = frozenset(
    {
        "user_id",
        "organization_id",
        "request_id",
        "trace_id",
        "span_id",
        "query",
        "prompt",
        "response",
        "sql",
        "sql_hash",
        "document_id",
        "chunk_id",
        "token",
        "secret",
        "password",
    }
)
```
Any attempt to pass dynamic identifiers as metric labels immediately raises `HighCardinalityViolationError`. Dynamic IDs are permitted exclusively in structured trace attributes and log events.

### Standard Platform Metrics
| Metric Name | Type | Description | Allowed Dimensions |
|-------------|------|-------------|-------------------|
| `http_requests_total` | Counter | Total HTTP requests processed | `method`, `route`, `status_code` |
| `http_request_duration_ms` | Histogram | Request latency distribution | `method`, `route` |
| `http_requests_in_flight` | Gauge | Active requests in-flight | `method` |
| `http_errors_total` | Counter | Total 4xx / 5xx responses | `method`, `route`, `status_code` |
| `analyst_requests_total` | Counter | Total AI Analyst queries | `route`, `status`, `language` |
| `analyst_route_total` | Counter | Distribution of selected routes | `route` (sql, rag, hybrid, none) |
| `analyst_duration_ms` | Histogram | End-to-end Analyst latency | `route`, `status` |
| `sql_queries_total` | Counter | Total SQL agent queries | `status` |
| `sql_query_duration_ms` | Histogram | Execution latency of SQL queries | `status` |
| `rag_requests_total` | Counter | Total RAG pipeline executions | `language`, `status` |
| `rag_duration_ms` | Histogram | RAG pipeline latency | `language`, `status` |
| `llm_requests_total` | Counter | Total LLM provider invocations | `provider`, `model`, `operation`, `status` |
| `llm_total_tokens` | Counter | Cumulative tokens consumed | `provider`, `model` |
| `ai_cost_total` | Counter | Total expenditure in USD | - |

---

## 6. Service Level Objectives (SLOs) & Error Budgets

The platform enforces declarative SLO definitions and deterministic error budget calculations:

$$\text{Error Budget Remaining} = 1.0 - \frac{\text{Actual Failure Rate}}{\text{Allowed Failure Rate}}$$

### Default Service Level Objectives
1. **Analyst Availability**: Target $\ge 99.0\%$.
2. **Analyst P95 Latency**: Target $\le 3000\text{ ms}$.
3. **SQL Success Rate**: Target $\ge 98.0\%$.
4. **RAG Success Rate**: Target $\ge 95.0\%$.
5. **LLM Success Rate**: Target $\ge 99.0\%$.

### Evaluation Status
- **`MET`**: Remaining budget $\ge 20\%$.
- **`WARNING`**: Remaining budget between $0\%$ and $20\%$.
- **`BREACHED`**: Remaining budget $< 0\%$.

---

## 7. Dependency Health Probes

Backing dependencies are independently probed for connectivity and round-trip latency:
- **PostgreSQL**: `check_database_connectivity`
- **Redis**: `check_redis_connectivity`
- **Qdrant**: `check_qdrant_connectivity`
- **LLM Provider**: In-memory status check

### Endpoints
- `GET /health/live`: Basic process liveness probe.
- `GET /health/ready`: Deep infrastructure readiness probe.
- `GET /health/dependencies`: Granular dependency status and latencies without failing unrelated routes.
- `GET /api/v1/observability/health`: Operational dependency health with RBAC controls.

---

## 8. Monitoring REST API

All operational endpoints reside under `/api/v1/observability/` and require appropriate RBAC permissions:

| Endpoint | Method | Required Permission | Description |
|----------|--------|---------------------|-------------|
| `/api/v1/observability/summary` | GET | `observability.read` | Aggregated metrics, latency percentiles, token usage, and total cost |
| `/api/v1/observability/metrics` | GET | `observability.metrics` | Prometheus exposition format (version 0.0.4) |
| `/api/v1/observability/health` | GET | `observability.health` | Dependency connectivity, status, and latencies |
| `/api/v1/observability/slos` | GET | `observability.read` | SLO compliance status and remaining error budgets |
| `/api/v1/observability/alerts` | GET | `observability.read` | Operational alert scans (high error rates, latency anomalies) |
| `/api/v1/observability/traces/{trace_id}` | GET | `observability.read` | Hierarchical spans for a specific trace with tenant boundary enforcement |

---

## 9. Security & Multi-Tenant Isolation

1. **Role-Based Access Control (RBAC)**:
   - `Admin` role: Full access to all telemetry, metrics, and trace inspection endpoints.
   - `Analyst` role: Access to summary, metrics, and health information.
   - `Viewer` / unauthorized users: HTTP 403 Forbidden.
2. **Tenant Boundary Enforcement**:
   - Trace spans store the executing tenant's `organization_id`.
   - Access to `/api/v1/observability/traces/{trace_id}` explicitly compares the trace's tenant against the caller's authenticated `organization_id`.
   - Any cross-tenant access attempt returns HTTP 403 Forbidden.

---

## 10. Data Retention & Persistence

Telemetry data is designed for retention efficiency:
- `LLMRequest` persistent table is correlated with `trace_id`, `span_id`, and `request_id` via Alembic migration `14cf751d60fd`.
- Discrete trace spans and events are maintained in in-memory bounded circular buffers (`deque(maxlen=...)`).
- Configuration `OBSERVABILITY_RETENTION_DAYS` specifies the intended retention window for audit logs and ledger entries.

---

## 11. Known Limitations

- **Trace Buffer Lifetime**: Distributed trace spans are currently buffered in bounded in-memory storage; distributed clusters require an external OTel collector for multi-node span aggregation.
- **Alert Dispatching**: Alert conditions are evaluated on query via `/api/v1/observability/alerts`; active webhook/Slack delivery is deliberately out of scope for this task.
