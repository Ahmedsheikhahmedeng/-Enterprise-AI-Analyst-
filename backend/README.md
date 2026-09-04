# Enterprise AI Analyst — Backend Foundation, Infrastructure, Data & Auth Architecture

> Tasks 0, 1, 2, 3 & 4: Production-oriented FastAPI backend with asynchronous PostgreSQL, Redis, Qdrant infrastructure connectivity, health probes, SQLAlchemy 2 ORM domain models, Alembic migrations, and Argon2id/JWT identity authentication with refresh token rotation and reuse detection.

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

## 🔐 Authentication System (Task 4)

The authentication system is dedicated strictly to **identity verification** (who the user is). RBAC and tenant-level authorization remain separated into Tasks 5 and 6.

### 1. Security Architecture
- **Argon2id Hashing**: Passwords are never stored or logged in plaintext. Baseline policy enforces $\ge 8$ characters.
- **Short-Lived JWT Access Tokens**: 15-minute lifespan (`ACCESS_TOKEN_EXPIRE_MINUTES`), containing `sub` (User UUID), `type: "access"`, `iat`, `exp`, and `jti`.
- **Hashed Refresh Token Sessions**: Refresh tokens are stored strictly as SHA-256 digests in PostgreSQL (`refresh_tokens`). Plaintext tokens exist only transiently at issuance time.
- **Token Rotation & Token Family Tracking**: Every refresh operation revokes the presented token and creates a new token session linked via `rotated_from_id` within a persistent `family_id`.
- **Reuse Detection**: Presenting an already-revoked refresh token triggers a security alert and immediately revokes the entire token family lineage, preventing session hijacking.
- **Enumeration Protection**: Registration and login endpoints emit generic error messages to prevent email enumeration.

### 2. API Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register a new user with Argon2id hash | No |
| `POST` | `/api/v1/auth/login` | Authenticate email/password, emit JWT + refresh token | No |
| `GET` | `/api/v1/auth/me` | Fetch authenticated caller profile (sanitized) | Yes (`Bearer`) |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token session, emit new token pair | No |
| `POST` | `/api/v1/auth/logout` | Revoke specific refresh token session | No |
| `POST` | `/api/v1/auth/logout-all` | Revoke all active refresh sessions for user | Yes (`Bearer`) |
| `POST` | `/api/v1/auth/change-password` | Update password and invalidate all active sessions | Yes (`Bearer`) |
| `POST` | `/api/v1/auth/forgot-password` | Issue single-use password reset token | No |
| `POST` | `/api/v1/auth/reset-password` | Consume reset token and set new password | No |
| `POST` | `/api/v1/auth/verify-email` | Confirm email with single-use verification token | No |
| `POST` | `/api/v1/auth/resend-verification` | Re-issue single-use verification token | No |

### 3. Environment Configuration
```env
JWT_SECRET_KEY="generate-a-secure-random-64-character-hex-key-for-production"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=60
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
```
*(In production, `JWT_SECRET_KEY` must be explicitly configured with at least 32 characters.)*

---

## 🛡️ Role-Based Access Control (RBAC) & Authorization (Task 5)

The authorization layer answers: **"What is this authenticated user allowed to do?"**
It builds on the authentication from Task 4 while maintaining strict architectural decoupling.

### 1. Authorization Architecture

```text
HTTP Request
     │
     ▼
[Authentication] ───► get_current_user (JWT Bearer Token validation)
     │                └── Yields 401 Unauthorized if missing, malformed, or expired
     ▼
[Context Resolution] ───► resolve_organization_context (via X-Organization-ID header)
     │                    └── Resolves single org or yields 403 Forbidden
     ▼
[Permission Check] ───► require_permission("documents.read")
     │                  └── Queries effective permissions in single SQL query
     │                  └── Yields 403 Forbidden with generic contract if unauthorized
     ▼
[Route Execution] ───► Service / Repository Layer
```

### 2. System Permission Catalog (26 Permissions)

| Category | Permissions | Description |
| :--- | :--- | :--- |
| **Users** | `users.read`, `users.manage`, `users.invite`, `users.remove` | User directory and administrative membership management |
| **Organization** | `organization.read`, `organization.manage` | Organization settings and configuration |
| **Documents** | `documents.read`, `documents.write`, `documents.delete`, `documents.manage` | Document upload, download, deletion, and pipeline administration |
| **Datasets** | `datasets.read`, `datasets.write`, `datasets.delete` | Structured data schemas and records management |
| **Data Sources** | `data_sources.read`, `data_sources.write`, `data_sources.delete` | External database and integration connectors |
| **Reports** | `reports.read`, `reports.create`, `reports.update`, `reports.delete` | Enterprise report generation, viewing, and deletion |
| **Analytics** | `analytics.read`, `analytics.execute` | Analytic metrics and query executions |
| **AI** | `ai.chat`, `ai.analyze` | Interactive chat and deep autonomous AI analysis |
| **Audit & Usage** | `audit.read`, `usage.read` | Organization audit logging and token consumption inspection |

### 3. Role Definitions & Default Mappings

- **`Admin`**: Full access to all 26 permissions across users, organization, data, AI, and audit.
- **`Analyst`**: Operational analytics and AI: `organization.read`, `documents.read/write`, `datasets.read/write`, `data_sources.read`, `reports.read/create`, `analytics.read/execute`, `ai.chat/analyze`.
- **`Viewer`**: Read-only visibility: `organization.read`, `documents.read`, `datasets.read`, `reports.read`, `analytics.read`, `ai.chat`.

### 4. Security Principles & Enforcement
- **401 vs 403**: Unauthenticated, invalid, or expired tokens always yield `401 Unauthorized`. Authenticated users lacking required permissions or valid tenant membership always yield `403 Forbidden`.
- **Generic Error Contract**: Authorization denial responses never leak required permission names:
  `{"error": {"code": "FORBIDDEN", "message": "You do not have permission to perform this action.", "request_id": "..."}}`
- **Context-Scoped Permissions**: A user can belong to multiple organizations with different roles (e.g. Analyst in Org A, Viewer in Org B). Permissions are strictly evaluated against the target organization context.
- **Cross-Organization Protection**: Roles scoped to Organization B cannot grant permissions to a member in Organization A.
- **No N+1 Queries**: Effective permissions are retrieved with a single joined query across `permissions`, `role_permissions`, `roles`, and `organization_members`.
- **Structured Audit Logging**: Authorization denials and role assignments/removals emit structured audit logs (`audit_event="role_assigned"`, `audit_event="authorization_denied"`) without logging sensitive secrets.

### 5. RBAC Seeding
Seed system permissions, roles, and default mappings idempotently:
```bash
python scripts/seed_rbac.py
```

### 6. Demonstration & Management Endpoints

| Method | Endpoint | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/admin/users` | `users.manage` | Admin user management access demonstration |
| `GET` | `/api/v1/rbac/test/read-document` | `documents.read` | Document read access demonstration |
| `POST` | `/api/v1/rbac/test/create-report` | `reports.create` | Report creation access demonstration |
| `GET` | `/api/v1/rbac/permissions` | Authenticated | Inspect caller's effective permissions for active organization |
| `GET` | `/api/v1/rbac/roles` | `organization.read` | List available system and organization roles |
| `POST` | `/api/v1/rbac/roles/assign` | `users.manage` | Assign or update member role in organization |
| `POST` | `/api/v1/rbac/roles/remove` | `users.manage` | Remove member role and membership in organization |


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
