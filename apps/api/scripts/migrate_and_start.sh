#!/bin/bash
set -e

# Ensure pip-installed binaries are in PATH
export PATH="/root/.local/bin:$PATH"

# Load .env.production if it exists (docker-compose env_file already sets these vars)
ENV_FILE="$(dirname "$0")/../.env.production"
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment from $ENV_FILE..."
    set -a
    . "$ENV_FILE"
    set +a
else
    echo "No .env.production found in container, relying on env_file from docker-compose..."
fi

echo "Running database migrations..."
/root/.local/bin/alembic upgrade head
echo "Migrations complete"

# Run the server. If args passed (e.g. from CMD), use them; otherwise default.
if [ $# -gt 0 ]; then
    echo "Starting server with provided args: $*"
    exec "$@"
else
    echo "Starting FastAPI server..."
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "${PORT:-8000}" \
        --workers "${WORKERS:-4}" \
        --no-access-log
fi
