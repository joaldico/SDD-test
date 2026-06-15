#!/bin/sh
# Container entrypoint — runs Alembic migrations then starts the API server.
# Executed as appuser (non-root) inside the runtime image.
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Migrations complete. Starting API server..."
exec uvicorn marketplace_conciliator.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
