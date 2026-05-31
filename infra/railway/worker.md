# Railway service: worker

Procrastinate background worker (`apps/worker`, package `health-worker`).

- **Root directory:** repository root (`/`). Required for the uv workspace.
- **Build command:** `uv sync --no-dev`
- **Start command:** `uv run procrastinate --app=health_worker.app worker`

## One-time database setup (before first run)

Procrastinate needs its tables created in Postgres once. Run this as a pre-deploy /
release command (or manually with `DATABASE_URL` set) before the worker starts:

```
uv run procrastinate --app=health_worker.app schema --apply
```

If the worker crash-loops on first deploy, this step has not been run yet.

## Environment variables

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | reference from `postgres` | The queue lives in Postgres. |

## Verify after deploy

- Worker process stays up (no crash loop) and logs that it is listening for jobs.
- M0 only requires the worker to run; the single registered task is a no-op.
