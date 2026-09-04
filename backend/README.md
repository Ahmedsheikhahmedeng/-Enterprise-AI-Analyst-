# Enterprise AI Analyst — Backend Foundation & Infrastructure

> Tasks 0, 1 & 2: Production-oriented FastAPI backend foundation with asynchronous PostgreSQL, Redis, Qdrant infrastructure connectivity, lifespan management, health/liveness/readiness probes, and Docker Compose topology.

---

## 🏗️ Architecture Baseline

This backend service strictly adheres to the architectural blueprint defined in [docs/architecture/task_0_backend_architecture.md](../docs/architecture/task_0_backend_architecture.md).

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

## 🧪 Quality & Testing Commands

Run the unit test suite:
```bash
pytest
```

Run integration tests against live infrastructure services (when Docker is running):
```bash
RUN_INTEGRATION_TESTS=true pytest tests/integration/
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
