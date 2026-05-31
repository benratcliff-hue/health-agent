# Railway services

These files describe the four Railway services for M0. They are reference for wiring
the services through the Railway UI (no Railway CLI required). One file per service:

- [postgres.md](postgres.md) - managed Postgres (provides `DATABASE_URL`).
- [api.md](api.md) - FastAPI backend.
- [worker.md](worker.md) - Procrastinate background worker.
- [web.md](web.md) - Next.js web app.

## Monorepo note

`api` and `worker` are Python members of one uv workspace, so their build must run
from the **repository root** (not `apps/api` / `apps/worker`), otherwise the
`health-db` workspace dependency will not resolve. `web` is self-contained and builds
from `apps/web`.

## Builder (verified 2026-05-30)

Railway builds these with **Railpack** (its current default builder), not Nixpacks.
Railpack detected Python and uv at the repo root with no extra config, so no Dockerfile
was needed.

The one required step per Python service: set a **Custom Start Command** in the service
UI (Settings -> Deploy). The repo-root `pyproject.toml` is a virtual workspace with no
entrypoint, so Railpack cannot infer a start command, and because all three code
services share one repo and root, a single repo-level start command (Procfile) would not
work. Each service's command is listed in its file below.

When generating a public domain, the target port is **8080** (`$PORT`'s default, which
both uvicorn and `next start` bind to via the start commands).

## Service dependency / env wiring

- `api` and `worker` need `DATABASE_URL` from the Postgres service (Railway reference
  variable).
- `web` needs `NEXT_PUBLIC_API_BASE_URL` pointing at the `api` service's public URL.
  This is a Next.js `NEXT_PUBLIC_` variable, so it is inlined at **build** time and must
  be present before the web build runs.
