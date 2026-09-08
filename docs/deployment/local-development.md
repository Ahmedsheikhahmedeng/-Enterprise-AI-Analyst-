# Local Development Guide

## 1. Quick Start with Docker Compose
To run the full stack locally with hot reload:

```bash
# 1. Start development backing services (PostgreSQL, Redis, Qdrant)
docker compose -f infra/compose/docker-compose.dev.yml up postgres redis qdrant -d

# 2. Or start the full stack including backend and frontend
docker compose -f infra/compose/docker-compose.dev.yml up -d
```

## 2. Running Locally with Python Virtual Environment & Node
If you prefer running services directly on the host:

### Backend
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Worker
```bash
cd backend
source .venv/bin/activate
python -m app.jobs.worker
```

### Frontend
```bash
cd frontend
npm run dev
```
Access the application at `http://localhost:3000`.
