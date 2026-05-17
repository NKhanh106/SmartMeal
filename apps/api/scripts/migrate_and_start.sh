#!/bin/bash
# Smart Meal — Database migration + zero-downtime startup script
# Usage: ./scripts/migrate_and_start.sh
set -e  # Exit immediately if any command fails

echo "🔄 Running database migrations..."
alembic upgrade head
echo "✅ Migrations complete"

echo "🚀 Starting FastAPI server..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WORKERS:-4}" \
  --loop uvloop \
  --no-access-log
