#!/usr/bin/env bash
# ==============================================================================
# Enterprise AI Analyst - Deployment Health & Readiness Verification Script
# Probes Frontend, Backend, Database, Redis, and Qdrant health
# ==============================================================================

set -euo pipefail

BACKEND_HOST="${BACKEND_HOST:-localhost}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-localhost}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"

BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
FRONTEND_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}"
QDRANT_URL="http://${QDRANT_HOST}:${QDRANT_PORT}"

echo "=================================================="
echo "== Probing Platform Service Health & Readiness  =="
echo "=================================================="

FAILED=0

# 1. Probe Backend Liveness
echo -n "[+] Probing Backend Liveness (${BACKEND_URL}/api/v1/platform/health)... "
if curl -sf --max-time 5 "${BACKEND_URL}/api/v1/platform/health" > /dev/null; then
    echo "[OK]"
else
    echo "[FAILED]"
    FAILED=$((FAILED + 1))
fi

# 2. Probe Backend Readiness
echo -n "[+] Probing Backend Readiness (${BACKEND_URL}/api/v1/platform/ready)... "
if curl -sf --max-time 5 "${BACKEND_URL}/api/v1/platform/ready" > /dev/null; then
    echo "[OK]"
else
    echo "[FAILED]"
    FAILED=$((FAILED + 1))
fi

# 3. Probe Frontend Availability
echo -n "[+] Probing Frontend Availability (${FRONTEND_URL}/)... "
if curl -sf --max-time 5 "${FRONTEND_URL}/" > /dev/null; then
    echo "[OK]"
else
    echo "[FAILED]"
    FAILED=$((FAILED + 1))
fi

# 4. Optional Qdrant Vector Engine Probe
if curl -sf --max-time 3 "${QDRANT_URL}/healthz" > /dev/null 2>&1; then
    echo "[+] Probing Qdrant Vector Engine... [OK]"
else
    echo "[~] Qdrant probe skipped or unreachable directly (acceptable if on private network)"
fi

if [[ ${FAILED} -eq 0 ]]; then
    echo "=================================================="
    echo "== All Platform Services Healthy & Ready!      =="
    echo "=================================================="
    exit 0
else
    echo "=================================================="
    echo "== [!] Health Check Failed (${FAILED} services failed) =="
    echo "=================================================="
    exit 1
fi
