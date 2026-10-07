.PHONY: up down test lint migrate seed

up:
	docker compose up --build

down:
	docker compose down -v

migrate:
	docker compose exec api alembic upgrade head

lint:
	cd apps/api && uv run ruff check . && uv run mypy app
	cd apps/mobile && npm run lint && npm run typecheck

test:
	cd apps/api && uv run pytest -q

test-pg:
	cd apps/api && DATABASE_URL_TEST=postgresql+asyncpg://shop:shop@localhost:5432/shopthereel_test uv run pytest -q

# Host-side DB URL (compose service names only resolve inside docker).
seed:
	cd apps/api && DATABASE_URL=postgresql+asyncpg://shop:shop@localhost:5432/shopthereel PYTHONPATH=. uv run python -m app.catalog.ingest --csv ../../data/raw/styles.csv --images ../../data/raw/images

seed-demo:
	cd apps/api && DATABASE_URL=postgresql+asyncpg://shop:shop@localhost:5432/shopthereel uv run python -m app.catalog.ingest --demo 200 --skip-images
