# ==============================================================================
# Enterprise AI Analyst - Production Backend Dockerfile
# Multi-stage, lean, hardened non-root container image
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

# Stage 2: Production Minimal Runtime
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000 \
    HOST="0.0.0.0" \
    ENVIRONMENT=production

# Install minimal runtime dependencies (e.g. curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create unprivileged system group and user
RUN groupadd --gid 10001 --system appgroup && \
    useradd --uid 10001 --gid appgroup --shell /usr/sbin/nologin --create-home --system appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source and migrations
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./alembic.ini

# Ensure non-root ownership
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Health check via standard platform health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/platform/health || exit 1

ENTRYPOINT ["uvicorn", "app.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
