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

## Builder uncertainty (verify when wiring)

Railway's default Nixpacks builder needs to recognise uv and the `uv.lock` file for the
Python services. Confirm this at setup time. If Nixpacks does not build the workspace
cleanly, the fallback is to add a small `Dockerfile` per Python service. Do not assume
the build commands below "just work" until you have seen a green deploy.

## Service dependency / env wiring

- `api` and `worker` need `DATABASE_URL` from the Postgres service (Railway reference
  variable).
- `web` needs `NEXT_PUBLIC_API_BASE_URL` pointing at the `api` service's public URL.
  This is a Next.js `NEXT_PUBLIC_` variable, so it is inlined at **build** time and must
  be present before the web build runs.
