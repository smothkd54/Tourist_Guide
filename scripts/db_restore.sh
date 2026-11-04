#!/usr/bin/env bash
# db_restore.sh — restore a PostgreSQL backup produced by backup.sh
#
# Usage:
#   DATABASE_URL=postgresql://... ./scripts/db_restore.sh /var/backups/pushkinskaya/db_20261103_030000.dump
#
# The dump is restored with --clean --if-exists, then migrations are re-applied
# so a dump taken before a schema change still converges to the current schema.

set -euo pipefail

DUMP="${1:-}"
if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
    echo "Usage: DATABASE_URL=... $0 <backup.dump>" >&2
    exit 2
fi
if [ -z "${DATABASE_URL:-}" ]; then
    echo "DATABASE_URL is not set." >&2
    exit 2
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Restoring $DUMP ..."
pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" "$DUMP"

echo "Applying migrations (no-op when the dump is current) ..."
cd "$PROJECT_DIR"
alembic upgrade head

echo "Verifying counts ..."
python scripts/seed_db.py --check
