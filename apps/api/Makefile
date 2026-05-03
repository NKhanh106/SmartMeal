.PHONY: install dev migrate test lint seed

install:
	python -m pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload

migrate:
	alembic upgrade head

test:
	pytest

lint:
	ruff check app tests

# Seed food nutrition data (Vietnamese foods for demo)
# Run AFTER migrate to populate the food_nutrition table.
# WARNING: Does not run in production ENVIRONMENT.
seed:
	python scripts/seed_food_data.py
