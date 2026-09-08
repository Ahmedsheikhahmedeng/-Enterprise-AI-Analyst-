#!/usr/bin/env bash
# ==============================================================================
# Enterprise AI Analyst - Database Migration Script
# Safely verifies schema compatibility and applies forward-only migrations
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${WORKSPACE_ROOT}/backend"

echo "=================================================="
echo "== Starting Database Migration Workflow       =="
echo "=================================================="

# Ensure database URL is provided
if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "[-] ERROR: DATABASE_URL environment variable is not set." >&2
    exit 1
fi

cd "${BACKEND_DIR}"

# 1. Safety Check: Verify Alembic model synchronization
echo "[+] Step 1/3: Verifying Alembic model and migration consistency (alembic check)..."
if python -m alembic check; then
    echo "[✓] Schema models and migrations are synchronized."
else
    echo "[-] WARNING: Alembic check detected divergence or pending model revisions." >&2
fi

# 2. Execute forward migration
echo "[+] Step 2/3: Applying forward migrations to head..."
if python -m alembic upgrade head; then
    echo "[✓] Database migrations successfully applied to head."
else
    echo "[-] CRITICAL: Migration failed! Halting deployment rollout." >&2
    echo "[-] Policy Notice: Automatic destructive downgrade is strictly prohibited." >&2
    exit 1
fi

# 3. Verify current revision
echo "[+] Step 3/3: Verifying current database revision..."
CURRENT_REV=$(python -m alembic current || true)
echo "[✓] Active database revision: ${CURRENT_REV}"
echo "=================================================="
echo "== Migration Completed Successfully             =="
echo "=================================================="
