# Personal Health Agent - developer entrypoints.
# Python is managed by uv (workspace at repo root); the web app by npm.

.PHONY: setup dev dev-api dev-web dev-worker db-up db-down test lint fmt

setup: ## Install all dependencies (Python workspace + web)
	uv sync
	cd apps/web && npm install

db-up: ## Start the local Postgres container in the background
	docker compose up -d db

db-down: ## Stop the local Postgres container
	docker compose down

# `dev` brings up the database and runs the api in the foreground. Run the web app and
# worker in separate terminals via `make dev-web` / `make dev-worker`. Keeping them as
# separate processes is simpler and clearer than orchestrating background jobs here.
dev: db-up dev-api

dev-api: ## Run the FastAPI api with reload (http://localhost:8000)
	uv run uvicorn health_api.main:app --reload --port 8000

dev-web: ## Run the Next.js web app (http://localhost:3000)
	cd apps/web && npm run dev

dev-worker: ## Run the Procrastinate worker (needs the DB up)
	uv run procrastinate --app=health_worker.app worker

test: ## Run unit tests
	uv run pytest

lint: ## Lint Python and web
	uv run ruff check .
	uv run ruff format --check .
	cd apps/web && npm run lint

fmt: ## Auto-format and auto-fix Python
	uv run ruff check --fix .
	uv run ruff format .
