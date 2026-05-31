# Railway service: api

FastAPI backend (`apps/api`, package `health-api`).

- **Root directory:** repository root (`/`). Required so the uv workspace resolves the
  `health-db` dependency.
- **Build command:** Railpack default (`uv sync`). `uv sync --no-dev` also fine.
- **Start command** (set in Settings -> Deploy):
  `uv run uvicorn health_api.main:app --host 0.0.0.0 --port $PORT`
- **Public domain target port:** `8080`.

## Environment variables

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | reference from `postgres` | Used by `/db-ping` and auth. |
| `CORS_ALLOW_ORIGINS` | the `web` service public URL | Comma-separated; lets the browser call the api. |
| `LOG_LEVEL` | `INFO` | Optional. |
| `SECRET_KEY` | strong random string | Signs session JWTs. Required; do not ship the dev default. |
| `API_BASE_URL` | this service's public URL | Used to build the magic-link URL in emails. |
| `WEB_BASE_URL` | the `web` service public URL | Post-login redirect target. |
| `AUTH_ALLOWED_EMAILS` | your email(s), comma-separated | Who may bootstrap a login (no public sign-up). |
| `COOKIE_SECURE` | `true` | Production is https. |
| `COOKIE_SAMESITE` | `none` | web and api are different domains (cross-site cookie). |
| `RESEND_API_KEY` | Resend API key | Without it the api falls back to logging emails instead of sending. |
| `EMAIL_FROM` | sender on a verified domain | e.g. `Health Agent <login@yourdomain>`. |

> **Cross-site cookie caveat:** with web and api on different Railway domains the session
> cookie is third-party (`SameSite=None`), which Safari/ITP can restrict. If logins do
> not stick in Safari, put both services under one parent domain (e.g. `app.x` and
> `api.x`) so the cookie is first-party. Verify before relying on it.

## Verify after deploy

- `GET /healthz` returns `200 {"status":"ok"}` from the public URL.
- `GET /db-ping` returns `200 {"status":"ok","result":1}` (proves the DB round-trip).
- After migrations have run (see worker), the magic-link login flow completes end to end.
