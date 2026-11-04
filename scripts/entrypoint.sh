#!/bin/sh
# Container entrypoint: migrate, seed, verify artifacts, then serve.
set -eu

if [ -n "${DATABASE_URL:-}" ]; then
    echo "Applying database migrations..."
    alembic upgrade head

    echo "Seeding the database if it is empty..."
    python scripts/seed_db.py --if-empty
else
    echo "DATABASE_URL is not set - serving the JSON catalogue (fallback mode)."
fi

# Fail fast and loud if required artifacts are missing, instead of starting
# a server that silently returns 503 on every /predict call.
python preflight_check.py

exec gunicorn -w "${GUNICORN_WORKERS:-2}" --timeout 120 -b 0.0.0.0:5000 backend.app:app
