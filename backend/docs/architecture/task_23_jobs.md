# TASK 23 — Production Background Jobs & Distributed Worker Architecture

## 1. Executive Summary
TASK 23 decouples computationally intensive and long-running platform operations from synchronous HTTP cycles into a resilient, scalable, observable, and multi-tenant background job architecture. Workloads transitioned to background execution include:
* **Document Ingestion** (`DocumentIngestionTask`)
* **Chunking** (`ChunkingTask`)
* **Embeddings** (`EmbeddingTask`)
* **Vector Indexing** (`VectorIndexingTask`)
* **Evaluation Benchmark Suites** (`EvaluationTask`)
* **Large Report Exports** (`ReportExportTask` producing PDF, HTML, Markdown, CSV to Object Storage)

Delivery semantics are explicitly guaranteed as **at-least-once** with deterministic, idempotent task handlers (avoiding unfounded claims of distributed exactly-once execution).

---

## 2. High-Level Architecture

```text
HTTP Request (Client / Internal Producer)
     │
     ▼
[JobDispatcher] ◄── Validates Payload & Enforces Size Limits (<64KB)
     │          ◄── Checks RBAC & Tenant Context Boundary
     │          ◄── Computes Canonical SHA-256 Payload Hash
     │          ◄── Checks Idempotency Conflict vs Reuse
     ▼
[PostgreSQL DB] ─── Durable State (`status: queued`, attempt: 0)
     │
     ▼
[JobQueue]      ─── RedisJobQueue (Production) / InMemoryJobQueue (Test)
     │              ├── Ready Queue (High, Normal, Low Priority)
     │              ├── In-Flight Reservation (Visibility Timeout + Worker Binding)
     │              └── Delayed ZSET (Exponential Backoff + Jitter)
     ▼
[Worker Pool]   ◄── Concurrency Semaphore & Per-Job-Type Semaphores
     │          ◄── Periodic Heartbeat Loop (TTL in Redis)
     │          ◄── Graceful Shutdown Handler (SIGTERM/SIGINT)
     ▼
[TaskRegistry]  ─── Decoupled Registry mapping `job_type` -> TaskHandler
     │
     ▼
[Task Handler]  ─── Adapters executing underlying domain services
     │              ├── IngestionService (TASK 8)
     │              ├── ChunkingService (TASK 9)
     │              ├── EmbeddingPipelineService (TASK 10)
     │              ├── VectorIndexingService (TASK 11)
     │              ├── BenchmarkRunner (TASK 20)
     │              └── ReportService & Exporters (TASK 19)
     │
     ▼
[JobLifecycle]  ─── State Transitions (`running` -> `completed` / `retry_scheduled` / `failed` / `dead_letter` / `cancelled`)
     │
     ▼
[Observability] ─── Low-cardinality Prometheus metrics, W3C trace propagation, and Audit logging
```

---

## 3. Core Components

### 3.1 Job Data Model (`jobs` Table)
* `id` (`UUID`): Primary Key.
* `organization_id` (`UUID`): Strict multi-tenant boundary.
* `created_by` (`UUID | None`): Initiating user ID (foreign key to `users.id`).
* `job_type` (`String(100)`): Job kind (`document_ingestion`, `chunking`, `embedding`, `vector_indexing`, `evaluation`, `report_export`).
* `status` (`String(50)`): Current lifecycle state.
* `priority` (`String(20)`): Scheduling priority (`high`, `normal`, `low`).
* `payload` (`JSONB`): Input arguments (strictly bounded to 64KB, sanitized of plain credentials).
* `result` (`JSONB`): Output summary (strictly bounded to 64KB; large exports reference object keys).
* `attempt` (`Integer`): Current execution attempt count.
* `max_attempts` (`Integer`): Allowed retry attempts before dead-lettering.
* `created_at`, `started_at`, `completed_at`, `cancelled_at`, `next_retry_at` (`DateTime(timezone=True)`).
* `error_code`, `error_message` (`String`, `Text`): Sanitized diagnostics without stack traces.
* `trace_id`, `request_id` (`String`): W3C distributed trace correlation.
* `idempotency_key` (`String(255)`): Client-provided deduplication identifier.
* `deduplication_hash` (`String(64)`): Canonical SHA-256 hash of the JSON payload.
* `worker_id` (`String(255)`): Active executing worker identifier.
* `progress` (`Float`): Normalized 0.0 to 1.0 task progress.
* `progress_message` (`String(255)`): Checkpoint status description.

### 3.2 Strict State Machine
Transitions are validated by `JobLifecycleManager`. Illegal transitions raise `InvalidJobStateTransitionError`.

```text
       ┌───────────┐
       │  queued   │──────────────┐
       └─────┬─────┘              │
             │                    │
             ▼                    ▼
       ┌───────────┐        ┌───────────┐
┌─────►│  running  │───────►│ cancelled │
│      └─────┬─────┘        └───────────┘
│            │ (on success)
│            ├─────────────────────────► ┌───────────┐
│            │                           │ completed │
│            │ (on transient error       └───────────┘
│            │  & attempts < max)
│            ▼
│      ┌─────────────────┐
│      │ retry_scheduled │
│      └─────┬───────────┘
│            │ (due timeout reached)
└────────────┘
             │ (on fatal error OR
             ▼  attempts >= max)
       ┌───────────┐
       │   failed  │
       └─────┬─────┘
             │
             ▼
       ┌─────────────┐
       │ dead_letter │
       └─────────────┘
```

Recovery transitions:
* `failed` $\to$ `queued` (manual retry)
* `dead_letter` $\to$ `queued` (manual retry)

### 3.3 Reliable Redis Queue (`RedisJobQueue`)
* **Ready Queues**: Multi-level priority queues (`jobs:ready:high`, `jobs:ready:normal`, `jobs:ready:low`).
* **In-Flight Reservation**: `jobs:inflight` (Redis ZSET with score = unix timestamp of visibility deadline).
* **Delayed Queue**: `jobs:delayed` (Redis ZSET with score = scheduled retry timestamp).
* **Housekeeping & Reclamation**: On dequeue, due delayed jobs are promoted to ready queues, and unacknowledged jobs exceeding visibility timeout are reclaimed back into ready queues automatically.
* **InMemoryJobQueue**: Thread-safe, identical-semantics queue used for deterministic testing and environments without external Redis brokers.

---

## 4. Operational Policies

### 4.1 Idempotency Guarantees
* Deduplication hash is computed using SHA-256 over canonical JSON (`json.dumps(sort_keys=True, separators=(",", ":"))`).
* If `idempotency_key` matches an existing job:
  * Same payload hash: Returns the existing job (replayed, zero duplicate work).
  * Differing payload hash: Rejects with `JobIdempotencyConflictError` (HTTP 409).

### 4.2 Retry Policy & Error Classification
* **Exponential Backoff**: `delay = min(max_delay, initial_delay * (backoff_factor ** (attempt - 1)))`.
* **Full Jitter**: Uniform random variation within $[0.5 \times delay, 1.5 \times delay]$ prevents thundering herds.
* **Retry Classification**:
  * *Retryable*: Connection drops, Redis timeouts, database pool exhaustion / lock timeouts, external provider 429/503.
  * *Non-Retryable*: Missing resources, invalid syntax, authorization / tenant violations, payload size violations, prompt injection detections. Non-retryable errors route immediately to `dead_letter`.

### 4.3 Cancellation Checkpoints
* Clients request cancellation via `POST /api/v1/jobs/{job_id}/cancel`.
* In-memory registry records cancelled job IDs.
* Task handlers check `context.is_cancelled()` at safe checkpoints between pipeline stages.
* Safely terminates execution and records status `cancelled` without leaving half-written records.

### 4.4 Tenant Isolation & RBAC
* Every job is strictly isolated to an `organization_id` derived from the database and authenticated `TenantContext`.
* Cross-tenant access to jobs is completely rejected (HTTP 404 / `JobNotFoundError`).
* RBAC Permissions:
  * `jobs.read`: View jobs, history, logs, and worker health (`Admin`, `Analyst`, `Viewer`).
  * `jobs.create`: Enqueue new background jobs (`Admin`, `Analyst`).
  * `jobs.cancel`: Cancel active/pending jobs (`Admin`, `Analyst`).
  * `jobs.retry`: Manually retry failed/dead-lettered jobs (`Admin`, `Analyst`).
  * `jobs.admin`: System worker and queue administration (`Admin`).

---

## 5. Observability & Telemetry

### 5.1 Low-Cardinality Prometheus Metrics
Prometheus metrics strictly avoid high-cardinality labels (`job_id`, `user_id`, `org_id`, `trace_id` are forbidden label keys):
* `jobs_total` (Counter, labels: `job_type`, `priority`)
* `jobs_completed_total` (Counter, labels: `job_type`)
* `jobs_failed_total` (Counter, labels: `job_type`)
* `jobs_retried_total` (Counter, labels: `job_type`)
* `jobs_cancelled_total` (Counter, labels: `job_type`)
* `jobs_dead_lettered_total` (Counter, labels: `job_type`)
* `job_duration_ms` (Histogram, labels: `job_type`, `status`)
* `job_attempts` (Histogram, labels: `job_type`)
* `worker_jobs_processed_total` (Counter)
* `worker_job_failures_total` (Counter)
* `queue_enqueue_total`, `queue_dequeue_total` (Counter, labels: `priority`)

### 5.2 Worker Health & Heartbeat
* Active workers write heartbeat timestamps to Redis key `jobs:worker:{worker_id}:heartbeat` with 45s TTL every 15s.
* `GET /api/v1/jobs/health` reports Redis connectivity, queue depths per priority, active worker count, and stuck job detections.

---

## 6. Failure Modes & Mitigations

| Failure Mode | Impact | Mitigation / System Behavior |
| :--- | :--- | :--- |
| **Worker Process Crash** | Job is reserved in-flight but never acknowledged | Visibility timeout expires in `jobs:inflight`; next polling worker automatically reclaims and re-enqueues the job. |
| **Redis Broker Unreachable** | Inability to push or pop from queues | Dispatcher persists durable record in PostgreSQL (`queued`); requests return controlled 503/error; background reconciler or manual retry enqueues when Redis recovers. |
| **Poison Pill Job (Corrupted data)** | Job crashes handler repeatedly | Max attempts bound execution; classified non-retryable or routed to `dead_letter` after `max_attempts` without blocking other jobs. |
| **High Queue Saturation** | Worker starvation and resource contention | Backpressure protection (`MAX_QUEUE_DEPTH`) rejects incoming submissions with `JobQueueFullError` (HTTP 429). |
| **Cross-Tenant IDOR Attempt** | Malicious actor queries or cancels another tenant's job | `JobSecurityPolicy.assert_tenant_access` and DB-level tenant filtering reject access with 404/JobNotFoundError. |
| **Accidental Credential Leakage** | Plain passwords/API keys placed in payload | `JobSecurityPolicy.validate_payload` scans keys and strings, rejecting with `SecurityPolicyViolationError`. |

---

## 7. Known Limitations & Future Work
1. **Scheduled / Cron Jobs**: Scheduled recurring jobs are intentionally out of scope for TASK 23 and will be addressed in future milestones.
2. **Distributed GPU Scheduler**: Dynamic GPU worker scheduling for deep learning inference remains out of scope.
3. **Automated Archive Worker**: Automatic database pruning based on `JOB_RETENTION_DAYS` is configured but batch cleanup is delegated to future maintenance workers.
