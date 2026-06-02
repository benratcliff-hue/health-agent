# Railway service: worker

Procrastinate background worker (`apps/worker`, package `health-worker`).

- **Root directory:** repository root (`/`). Required for the uv workspace.
- **Build command:** Railpack default (`uv sync`). `uv sync --no-dev` also fine.
- **Pre-deploy command** (Settings -> Deploy): runs migrations before the worker starts.
  The worker is the natural home for this since its environment has health-db, alembic,
  and procrastinate:

  ```
  uv run alembic -c packages/db/alembic.ini upgrade head
  ```

- **Start command** (set in Settings -> Deploy):

  ```
  uv run procrastinate --app=health_worker.app worker
  ```

## Migrations (M1)

`alembic upgrade head` is idempotent and applies both the app tables and the procrastinate
queue schema. This retires the M0 `schema --apply || true` start-command shortcut. When
upgrading an environment that still has the M0 worker config, switch the start command to
the plain worker above and add the pre-deploy command.

The app tables must exist before the api can serve auth requests, so make sure this
pre-deploy has run once after deploying M1.

## Environment variables

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | reference from `postgres` | The queue lives in Postgres. |
| `ENCRYPTION_KEY` | same Fernet key as the api | Decrypts OAuth tokens for Whoop sync. |
| `WHOOP_CLIENT_ID` / `WHOOP_CLIENT_SECRET` | same as the api | Token refresh during backfill/sync. |
| `WHOOP_API_BASE` | `https://api.prod.whoop.com` | Default. |
| `ANTHROPIC_API_KEY` | same as the api | Generates briefings (absent → stub text). |
| `COACH_MODEL` | `claude-haiku-4-5` | Optional; default. |
| `RESEND_API_KEY` / `EMAIL_FROM` | same as the api | Delivers the briefing emails. |

## Briefings (5b)

The worker runs a periodic task (`dispatch_briefings`, every 15 min) that enqueues a
`generate_briefing` job for each user whose **06:00** (morning) or **20:00** (evening)
local time — from `household.timezone` — falls in the current window. Generation is
idempotent per (user, kind, local day). This needs the Anthropic + Resend env vars above;
without them the worker still runs but uses the stub coach / logs the email.

## Verify after deploy

- Worker process stays up (no crash loop) and logs that it is listening for jobs.
- M0 only requires the worker to run; the single registered task is a no-op.
