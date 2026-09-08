# Production Architecture & Deployment Guide

## 1. System Overview
The Enterprise AI Analyst production system is architected as an immutable, multi-tier containerized stack running on standard Docker and Docker Compose infrastructure.

```text
[ Internet / Enterprise Clients ]
                │
                ▼ (HTTPS / 443)
┌──────────────────────────────────────────────┐
│ Reverse Proxy (TLS Termination, HSTS, SSE)   │
└───────┬──────────────────────────────┬───────┘
        │ (HTTP / 3000)                │ (HTTP / 8000)
        ▼                              ▼
┌──────────────────┐           ┌──────────────────┐
│ Next.js Frontend │           │ FastAPI Backend  │
│ (Non-root, Node) │           │ (Non-root, Py)   │
└──────────────────┘           └───────┬──────────┘
  [frontend_net]                       │ [backend_net]
                                       ▼
                               ┌──────────────────┐
                               │ Job Worker       │
                               │ (Async Tasks)    │
                               └───────┬──────────┘
                                       │ [data_net]
       ┌───────────────────────────────┴───────────────────────────────┐
       ▼                               ▼                               ▼
┌──────────────┐               ┌──────────────┐               ┌──────────────┐
│  PostgreSQL  │               │    Redis     │               │    Qdrant    │
│  (Data Volume│               │  (AppendOnly │               │ (Vector Store│
│  Private Net)│               │  Private Net)│               │  Private Net)│
└──────────────┘               └──────────────┘               └──────────────┘
```

## 2. Network Segmentation
Three isolated Docker bridge networks enforce strict least-privilege boundary rules:
1. **`frontend_net`**: Connects Frontend container and Backend API.
2. **`backend_net`**: Connects Backend API and Worker process for coordination.
3. **`data_net` (`internal: true`)**: Private network connecting Backend and Worker directly to PostgreSQL, Redis, and Qdrant. No external gateway or public ports are bound to the host.

## 3. Container Hardening
All production containers adhere to enterprise security baselines:
- **Non-Root Execution**: Backend and Worker run as `appuser` (UID 10001); Frontend runs as `nextjs` (UID 10001).
- **Capability Dropping**: `cap_drop: [ALL]` drops Linux kernel capabilities.
- **Privilege Escalation Prevention**: `security_opt: [no-new-privileges:true]`.
- **Explicit Resource Limits**: CPU, memory, and PID limits are enforced per container to prevent resource starvation.

## 4. Launching the Production Stack
```bash
# 1. Copy and configure environment secrets
cp .env.production.example .env.production
chmod 600 .env.production
# Edit .env.production with your high-entropy production secrets

# 2. Run pre-deployment database migration
bash infra/scripts/migrate.sh

# 3. Launch the container stack
docker compose -f infra/compose/docker-compose.prod.yml --env-file .env.production up -d

# 4. Verify deployment health
bash infra/scripts/healthcheck.sh
```
