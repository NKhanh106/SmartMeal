install:
	pnpm install

dev-web:
	pnpm --filter web dev

dev-api:
	cd apps/api && uvicorn app.main:app --reload

test-api:
	cd apps/api && pytest

migrate-api:
	cd apps/api && alembic upgrade head
