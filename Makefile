.PHONY: up down test lint migrate seed

up:
	docker compose up --build

down:
	docker compose down -v

migrate:
	cd apps/api && uv run alembic upgrade head

lint:
	cd apps/api && uv run ruff check . && uv run mypy app
	cd apps/mobile && npm run lint && npm run typecheck

test:
	cd apps/api && uv run pytest -q

seed:
	@echo "Phase 3: dataset seed (not in Phase 1)"
