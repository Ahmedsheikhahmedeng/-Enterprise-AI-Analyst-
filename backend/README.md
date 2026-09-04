# Enterprise AI Analyst — Backend Foundation, Infrastructure & Data Architecture

> Tasks 0, 1, 2 & 3: Production-oriented FastAPI backend with asynchronous PostgreSQL, Redis, Qdrant infrastructure connectivity, health probes, SQLAlchemy 2 ORM domain models, and Alembic database migrations.

---

## 🏗️ Architecture Baseline

This backend service strictly adheres to the architectural blueprint defined in [docs/architecture/task_0_backend_architecture.md](../docs/architecture/task_0_backend_architecture.md).

---

## 🗄️ PostgreSQL Data Model & Alembic Migrations (Task 3)

### 1. Domain Entities (19 Models)

The relational data model is built using modern **SQLAlchemy 2 (`Mapped[]`, `mapped_column()`, `relationship()`)** with strict UUID primary keys and timezone-aware timestamps (`TIMESTAMP WITH TIME ZONE`):

| Domain Area | Table Name | Key Attributes & Constraints |
| :--- | :--- | :--- |
| **Tenancy & IAM** | `organizations` | `slug` (unique), `name`, `is_active` |
| | `users` | `email` (unique), `password_hash`, `first_name`, `last_name` |
| | `roles` | Scoped to `organization_id`, `name`, `description` |
| | `permissions` | `name` (unique, e.g. `documents.read`, `reports.create`) |
| | `role_permissions` | Composite PK (`role_id`, `permission_id`) association table |
| | `organization_members` | Composite unique (`organization_id`, `user_id`), assigned `role_id` |
| **Unstructured Data** | `documents` | Scoped to `organization_id`, file metadata, `status`, indexed on `(organization_id, created_at)` |
| | `document_chunks` | Scoped to `organization_id`, `document_id`, `chunk_index`, text content, `metadata` (JSONB) |
| **Structured Data** | `datasets` | Scoped to `organization_id`, `source_type`, `status`, `row_count` |
| | `dataset_columns` | Composite unique (`dataset_id`, `name`), `data_type`, `ordinal_position` |
| | `data_sources` | Scoped to `organization_id`, `type`, `status`, `configuration` (JSONB) |
| **AI Conversations** | `conversations` | Scoped to `organization_id`, `user_id`, `title`, indexed on `(organization_id, created_at)` |
| | `messages` | Linked to `conversation_id`, `role` (`user`/`assistant`/`tool`), indexed on `(conversation_id, created_at)` |
| **Analysis Engine** | `analysis_runs` | Scoped to `organization_id`, optional `conversation_id`, `query`, status, timestamps |
| | `analysis_steps` | Linked to `analysis_run_id`, composite unique `(analysis_run_id, step_order)`, JSONB payloads |
| **Outputs & Auditing** | `reports` | Scoped to `organization_id`, generated markdown/JSON content, links to `analysis_run_id` |
| | `audit_logs` | Append-only tenant audit stream (`organization_id`, `user_id`, `action`, `resource_type`, `metadata`) |
| | `usage_events` | Granular operational events (`organization_id`, `event_type`, `quantity`, `metadata`) |
| | `llm_requests` | Cost and latency tracking per LLM inference (`model`, tokens, `estimated_cost`, `latency_ms`) |

### 2. Multi-Tenant Architecture
- Every tenant-owned table explicitly includes `organization_id` (foreign key to `organizations.id` with `ON DELETE RESTRICT` or `CASCADE` depending on business domain).
- Global/system resources (`users`, `permissions`) remain outside direct tenant scoping; user membership is maintained through `organization_members`.
- Queries enforce multi-tenant isolation through composite indexes such as `(organization_id, created_at)`.

---

## 📦 Backing Infrastructure Services (Task 2)

| Service | Engine Version | Role in Architecture |
| :--- | :--- | :--- |
| **PostgreSQL** | `16-alpine` | Primary transactional and relational store for users, orgs, datasets, and audits. |
| **Redis** | `7-alpine` | High-speed cache, distributed rate limiting, and async broker. |
| **Qdrant** | `latest` | High-performance vector database powering dense and sparse hybrid retrieval. |

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- Python 3.12+
- Docker & Docker Compose (for local containerized infrastructure)

### 2. Environment Configuration
Copy the sample environment configuration:
```bash
cp .env.example .env
```

### 3. Install Python Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 4. Docker Compose Operations
Start all backing infrastructure services and backend container:
```bash
docker compose up --build -d
```

Check container status and health probes:
```bash
docker compose ps
```

View aggregated service logs:
```bash
docker compose logs -f
```

Stop containers gracefully:
```bash
docker compose down
```

Stop containers and remove persistent volumes (resets PostgreSQL and Qdrant data):
```bash
docker compose down -v
```

### 5. Running Natively (Without Containerized Backend)
If backing services are running natively or in standalone containers:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🩺 Health Check Endpoints

| Endpoint | Purpose | Semantics |
| :--- | :--- | :--- |
| `GET /api/v1/health` | Basic Service Health | Backward-compatible baseline health returning service name and version. |
| `GET /api/v1/health/live` | Liveness Probe | Indicates the application event loop is alive and responsive. |
| `GET /api/v1/health/ready` | Readiness Probe | Evaluates reachability of **PostgreSQL**, **Redis**, and **Qdrant**. Returns `200 OK` when all dependencies are reachable, or `503 Service Unavailable` if any dependency is offline. |

---

## 🗃️ Database Migrations (Alembic)

Run database migrations to latest schema version:
```bash
alembic upgrade head
```

Rollback the most recent migration step:
```bash
alembic downgrade -1
```

Generate a new migration script following model changes:
```bash
alembic revision --autogenerate -m "describe_changes"
```

---

## 🧪 Quality & Testing Commands

Run the unit test suite:
```bash
pytest tests/unit/
```

Run database integration tests against PostgreSQL:
```bash
pytest tests/integration/test_database_models.py
```

Run infrastructure integration tests against live Docker services:
```bash
RUN_INTEGRATION_TESTS=true pytest tests/integration/
```

Run full test suite:
```bash
pytest
```

Run linter and formatting checks:
```bash
ruff check .
ruff format --check .
```

Run static type checking with MyPy:
```bash
mypy app tests
```

Verify syntax compilation:
```bash
python -m compileall app
```
