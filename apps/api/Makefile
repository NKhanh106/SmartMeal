.PHONY: install dev migrate test lint

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
