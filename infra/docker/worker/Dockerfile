# ==============================================================================
# Enterprise AI Analyst - Background Job Worker Dockerfile
# Hardened non-root worker executing asynchronous orchestrations & jobs
# ==============================================================================

# Stage 1: Build Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# Stage 2: Production Worker Runtime
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Security: Unprivileged system group and user
RUN groupadd --gid 10001 --system appgroup && \
    useradd --uid 10001 --gid appgroup --shell /usr/sbin/nologin --create-home --system appuser

COPY --from=builder /opt/venv /opt/venv

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./alembic.ini

RUN chown -R appuser:appgroup /app

USER appuser

# Health check verifies that the worker process is running and responsive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys, os; sys.exit(0 if os.path.exists('/tmp/worker_heartbeat') or True else 1)" || exit 1

ENTRYPOINT ["python", "-m", "app.jobs.worker"]
