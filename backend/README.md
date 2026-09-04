# Enterprise AI Analyst — Backend Foundation

> Task 1: Clean, production-oriented FastAPI foundation with structured logging, configuration validation, standard exception envelopes, and health checks.

---

## 🏗️ Architecture Baseline

This backend service follows the architectural principles defined in [docs/architecture/task_0_backend_architecture.md](../docs/architecture/task_0_backend_architecture.md).

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- Python 3.12+
- Docker & Docker Compose (optional for containerized runtime)

### 2. Environment Configuration
Copy the sample environment variables:
```bash
cp .env.example .env
```

### 3. Install Dependencies
Create and activate a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 4. Run Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be accessible at:
- Swagger UI: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- ReDoc: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## 🧪 Quality & Testing Commands

Run the full automated test suite:
```bash
pytest
```

Run code formatting and linter checks with Ruff:
```bash
ruff check .
ruff format --check .
```

Run static type checking with MyPy:
```bash
mypy app
```

Verify syntax and compile all application modules:
```bash
python -m compileall app
```

---

## 🐳 Docker Deployment

Build the container image:
```bash
docker build -t enterprise-ai-analyst-backend .
```

Run the container:
```bash
docker run -p 8000:8000 --env-file .env enterprise-ai-analyst-backend
```

Run via Docker Compose:
```bash
docker compose up --build
```
