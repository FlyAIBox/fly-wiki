#!/usr/bin/env bash
# Single entrypoint for the API and Worker roles so both share one pinned image.
# Usage: entrypoint.sh [api|worker|migrate|shell]
set -euo pipefail

role="${1:-api}"

run_migrations() {
  echo "[entrypoint] applying database migrations"
  alembic upgrade head
}

case "$role" in
  api)
    # The API owns schema migrations so a single-command boot converges the DB.
    run_migrations
    exec uvicorn flywiki.main:app --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec celery -A flywiki.tasks.celery_app.celery_app worker --loglevel=info
    ;;
  migrate)
    run_migrations
    ;;
  shell)
    exec "${@:2}"
    ;;
  *)
    echo "[entrypoint] unknown role: $role" >&2
    echo "[entrypoint] expected one of: api worker migrate shell" >&2
    exit 64
    ;;
esac
