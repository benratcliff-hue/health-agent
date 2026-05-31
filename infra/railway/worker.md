# Railway service: worker

Procrastinate background worker (`apps/worker`, package `health-worker`).

- **Root directory:** repository root (`/`). Required for the uv workspace.
- **Build command:** Railpack default (`uv sync`). `uv sync --no-dev` also fine.
- **Start command** (set in Settings -> Deploy):

```
sh -c "uv run procrastinate --app=health_worker.app schema --apply || true; exec uv run procrastinate --app=health_worker.app worker"
```

## Schema note (M0 shortcut)

Procrastinate needs its queue tables created in Postgres once. The start command above
applies the schema on first boot and harmlessly skips it on later boots (the `|| true`
swallows the "already exists" error), then `exec`s the worker. This avoids a crash loop
without needing CLI access for a one-off command.

In M1 this is replaced by proper migrations (Alembic for app tables, `procrastinate`
migrations for the queue) run as a pre-deploy step, and the start command drops back to
just `uv run procrastinate --app=health_worker.app worker`.

## Environment variables

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | reference from `postgres` | The queue lives in Postgres. |

## Verify after deploy

- Worker process stays up (no crash loop) and logs that it is listening for jobs.
- M0 only requires the worker to run; the single registered task is a no-op.
