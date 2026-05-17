# Smart Meal — Production Deployment Runbook

> **Audience:** DevOps / Platform Engineer
> **Stack:** Next.js 15 + FastAPI + PostgreSQL 16 + Redis 7 + Groq + Gemini
> **Last updated:** 2026-05-07

---

## Prerequisites

Before deploying, ensure you have:

- [ ] Docker Engine 24+ and Docker Compose v2
- [ ] Domain name configured with DNS A/AAAA records pointing to your server
- [ ] SSL/TLS certificates (via Let's Encrypt or your provider)
- [ ] `.env.production` files created from `.env.production.example` templates
  - [ ] `apps/api/.env.production` — backend secrets
  - [ ] `apps/web/.env.production` — frontend public env vars
- [ ] Database backup of production database (if migrating from existing system)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Client (Browser)                     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Nginx / Reverse Proxy (Terminating TLS)   │
│         - Serves Next.js static on port 443            │
│         - Proxies /api/* → FastAPI on port 8000       │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────┐      ┌──────────────────────────┐
│   Next.js Frontend   │      │    FastAPI Backend       │
│   (Port 3000)        │      │    (Port 8000)            │
│   Node 20 Alpine     │      │    Python 3.12 Alpine     │
└──────────────────────┘      └─────┬──────────┬──────────┘
                                    │          │
                                    ▼          ▼
                          ┌────────────┐  ┌───────────┐
                          │ PostgreSQL │  │   Redis   │
                          │  (port 5432)│  │ (port 6379)│
                          └────────────┘  └───────────┘
```

---

## 1. Pre-deployment Checklist

Run through this checklist before every deployment:

- [ ] All tests pass locally:
  ```bash
  # Backend
  cd apps/api && pytest

  # Frontend
  cd apps/web && npm run lint && npm run build
  ```
- [ ] `.env.production` files are configured (do NOT commit these files)
- [ ] Database backup has been created
- [ ] Team has been notified of maintenance window
- [ ] Rollback plan is documented and tested

---

## 2. Environment Configuration

### Backend — `apps/api/.env.production`

Copy from the template and fill in real values:

```bash
cp apps/api/.env.production.example apps/api/.env.production
```

Critical values that MUST be changed:

```bash
SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_urlsafe(64))">
POSTGRES_PASSWORD=<strong random password, min 16 chars>
POSTGRES_USER=smartmeal_user       # create this user in Postgres first
POSTGRES_HOST=<your-db-host>
REDIS_URL=redis://<your-redis-host>:6379/0

GROQ_API_KEY=gsk_...              # from console.groq.com
GEMINI_API_KEY=AIza...            # from aistudio.google.com

BACKEND_CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

### Frontend — `apps/web/.env.production`

```bash
cp apps/web/.env.production.example apps/web/.env.production
```

```bash
NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com
NEXT_PUBLIC_APP_NAME=Smart Meal
```

> **Security note:** Only variables prefixed with `NEXT_PUBLIC_` are exposed to the browser. Never put API keys here.

### Create PostgreSQL user and database

```bash
psql -h <your-db-host> -U postgres -c "
  CREATE USER smartmeal_user WITH PASSWORD 'your_strong_password';
  CREATE DATABASE smartmeal_prod OWNER smartmeal_user;
  GRANT ALL PRIVILEGES ON DATABASE smartmeal_prod TO smartmeal_user;
"
```

---

## 3. Build Images

```bash
# Pull latest code first
git pull origin main

# Build all images
docker-compose -f docker-compose.production.yml build
```

Expected build time: 3–5 minutes (first run), ~30 seconds (subsequent with cache).

---

## 4. Database Migration

### Dry-run (recommended before first deploy)

```bash
docker-compose -f docker-compose.production.yml run --rm api \
  alembic upgrade head --sql | head -100
```

Review the SQL output carefully before proceeding.

### Apply migrations

```bash
docker-compose -f docker-compose.production.yml run --rm api \
  alembic upgrade head
```

Expected output:
```
Running in PRODUCTION mode
[alembic.output] Running upgrade  → <latest_revision>
```

---

## 5. Deploy with Zero Downtime

Deploy the API first, wait for it to be healthy, then deploy the frontend:

```bash
# 1. Deploy API
docker-compose -f docker-compose.production.yml up -d --no-deps api
echo "Waiting 15s for API to initialize..."
sleep 15

# 2. Verify API health
curl -s http://localhost:8000/health | jq .

# 3. Deploy frontend
docker-compose -f docker-compose.production.yml up -d --no-deps frontend
echo "Waiting 10s for frontend to initialize..."
sleep 10

# 4. Verify frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```

Expected: `200`

---

## 6. Post-deployment Verification

Run the health monitor and security header tests:

```bash
# Health checks
./scripts/health_monitor.sh http://localhost:8000

# Security headers
./scripts/test_security_headers.sh http://localhost:8000 http://localhost:3000
```

### Manual smoke tests

```bash
# 1. Basic health
curl -s http://localhost:8000/health

# 2. Readiness (DB + Redis)
curl -s http://localhost:8000/health/ready | jq .

# 3. AI health (no auth required)
curl -s http://localhost:8000/health/ai | jq .

# 4. API docs (should return 404 in production)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs

# 5. OpenAPI JSON (should return 404 in production)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/openapi.json

# 6. Frontend loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```

All should return `200` except `/docs` and `/openapi.json` which should return `404` in production.

---

## 7. Rollback Procedure

### Option A: Rollback to previous Docker image

```bash
# Find the previous image tag
docker images | grep smartmeal

# Tag previous image as current
docker tag smartmeal_api:<previous-tag> smartmeal_api:latest
docker tag smartmeal_frontend:<previous-tag> smartmeal_frontend:latest

# Redeploy
docker-compose -f docker-compose.production.yml up -d --no-deps api
sleep 10
docker-compose -f docker-compose.production.yml up -d --no-deps frontend
```

### Option B: Rollback database migration

```bash
# Check current migration
docker-compose -f docker-compose.production.yml exec api \
  alembic current

# Rollback one revision
docker-compose -f docker-compose.production.yml exec api \
  alembic downgrade -1

# If you need to roll back to a specific revision
docker-compose -f docker-compose.production.yml exec api \
  alembic downgrade <revision_hash>
```

### Option C: Full rollback via git

```bash
git revert HEAD           # Create revert commit (preferred)
# OR
git checkout <previous-commit-hash>
git push origin main

# Rebuild and redeploy
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d
```

---

## 8. Monitoring

### Prometheus Metrics

Metrics are exposed at `/metrics` when `ENVIRONMENT=production`:

```bash
curl http://localhost:8000/metrics
```

Key metrics:
- `http_requests_total{method, endpoint, status}` — request count
- `http_request_duration_seconds` — request latency histogram
- `http_requests_in_progress` — concurrent requests

### Health Monitor Script

Run periodically via cron (every 5 minutes):

```bash
# In crontab -e
*/5 * * * * /app/scripts/health_monitor.sh >> /var/log/smartmeal_health.log 2>&1
```

### Log Aggregation

Logs are written to stdout (captured by Docker):

```bash
# View API logs
docker-compose -f docker-compose.production.yml logs -f api

# View recent errors only
docker-compose -f docker-compose.production.yml logs --since=10m api | grep -i error
```

---

## 9. Environment Variables Reference

### Backend (`apps/api/.env.production`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | Yes | `development` | Set to `production` |
| `SECRET_KEY` | Yes | — | Min 32 chars, use `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DATABASE_URL` | Yes | — | Full connection string |
| `POSTGRES_HOST` | Yes | `localhost` | Database host |
| `POSTGRES_PASSWORD` | Yes | — | Database password |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL |
| `GROQ_API_KEY` | Yes | — | From console.groq.com |
| `GEMINI_API_KEY` | Yes | — | From aistudio.google.com |
| `BACKEND_CORS_ORIGINS` | Yes | — | JSON array of allowed origins |
| `LOG_LEVEL` | No | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `DEBUG` | No | `false` | Set to `false` in production |
| `PORT` | No | `8000` | Container port |
| `WORKERS` | No | `4` | uvicorn worker count |

### Frontend (`apps/web/.env.production`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | — | Backend API base URL (no trailing slash) |
| `NEXT_PUBLIC_APP_NAME` | No | `Smart Meal` | App display name |

---

## 10. Troubleshooting

### API returns 500 on startup

Check logs:
```bash
docker-compose -f docker-compose.production.yml logs api | tail -50
```

Common causes:
- `SECRET_KEY` is still the dev default — check `.env.production`
- Database connection failed — verify `DATABASE_URL`
- Missing `GROQ_API_KEY` or `GEMINI_API_KEY`

### Frontend shows "Network Error" or 500 on API calls

1. Verify backend is healthy: `curl http://localhost:8000/health`
2. Check CORS: ensure `BACKEND_CORS_ORIGINS` includes the frontend domain
3. Check that `NEXT_PUBLIC_API_BASE_URL` in frontend `.env.production` matches the actual API URL

### Database migration fails

```bash
# Check current state
docker-compose -f docker-compose.production.yml exec api \
  alembic current

# Check pending migrations
docker-compose -f docker-compose.production.yml exec api \
  alembic history

# If stuck, try stamp to current revision without running
docker-compose -f docker-compose.production.yml exec api \
  alembic stamp <current_revision>
```

### Redis connection errors

Ensure Redis is reachable:
```bash
docker-compose -f docker-compose.production.yml exec api \
  python -c "import asyncio; from app.core.cache import get_redis; asyncio.run(get_redis().ping())"
```

### Frontend build fails

Common on first build:
```bash
cd apps/web
npm ci               # Clean install
npm run build        # Production build
```

Check for TypeScript errors:
```bash
npm run lint
npx tsc --noEmit
```
