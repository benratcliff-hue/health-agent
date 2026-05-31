# health-agent

Personal Health Agent: a two-person longitudinal health system. Ingests wearable and
app data into Postgres and exposes a conversational coach plus scheduled briefings.

The source of truth for product and architecture is [docs/PRD.md](docs/PRD.md).

**Status: M0** (repo, CI, local + Railway hello-world across web, api, worker, postgres).
No auth, ingest, Whoop, chat, or LLM calls yet; those start in M1.

## Layout

Monorepo (PRD section 13):

```
apps/
  web/      Next.js web app (status page in M0)
  api/      FastAPI backend (/healthz, /db-ping)
  worker/   Procrastinate worker (one no-op task in M0)
  cron/     scheduled entrypoints (placeholder, M1)
packages/
  shared/   shared types/constants/prompts (placeholder, M1)
  db/        SQLAlchemy engine now; models + migrations in M1
infra/railway/   per-service Railway wiring notes
docs/            PRD and setup guides
```

The Python apps (`api`, `worker`) and packages form one
[uv](https://docs.astral.sh/uv/) workspace rooted at the repo root, so a single
`uv sync` builds one virtual environment with one lockfile. We use uv (over Poetry)
because it manages the Python toolchain, dependencies, and lockfile with one fast tool,
which keeps a solo-maintained repo simple.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (`brew install uv`) - manages Python 3.12+ and deps.
- Node.js 20+ and npm - for the web app.
- Docker - runs local Postgres via `docker compose`.

## Setup

```bash
cp .env.example .env        # adjust if needed; defaults match docker-compose
make setup                  # uv sync + npm install in apps/web
make db-up                  # start local Postgres
make migrate                # create app tables + procrastinate queue schema
```

Set `AUTH_ALLOWED_EMAILS` in `.env` to your email so you can sign in (there is no public
sign-up).

## Run locally

Each command runs in its own terminal.

```bash
make dev          # starts local Postgres (Docker) + the api on :8000
make dev-web      # the Next.js app on :3000
make dev-worker   # the Procrastinate worker (see note below)
```

Then open <http://localhost:3000> - the page probes the api and should show green
checks for both `/healthz` and `/db-ping`.

Direct api checks:

```bash
curl localhost:8000/healthz    # {"status":"ok"}
curl localhost:8000/db-ping    # {"status":"ok","result":1}
```

### Sign in locally

With `make dev` running and your email in `AUTH_ALLOWED_EMAILS`, open
<http://localhost:3000/login>, enter that email, and submit. The console email sender
prints the login link to the api logs (the `make dev` terminal); open it to land on
`/me` signed in.

### Worker note

The worker's queue tables are created by `make migrate` (the queue schema is part of the
Alembic migrations). After migrating, just run `make dev-worker`.

## Test, lint, format

```bash
make test    # pytest (the live DB test is skipped unless DATABASE_URL is set)
make lint    # ruff check + ruff format --check (Python), eslint (web)
make fmt     # ruff auto-fix + format (Python)
```

To run the live database test locally, start Postgres and export the URL:

```bash
make db-up
DATABASE_URL=postgresql://health:health@localhost:5432/health uv run pytest
```

## CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every PR (and pushes to
`main`) using free GitHub-hosted runners: a Python job (ruff + pytest against a Postgres
service container) and a web job (eslint + `next build`).

## Deployment

All services run on Railway. Per-service build/run commands and env wiring are in
[infra/railway/](infra/railway/). Services are wired through the Railway UI.
