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
| `API_BASE_URL` | the `web` URL + `/api` | Builds the magic-link URL; routed through the web proxy so the login cookie is first-party. e.g. `https://<web>/api`. |
| `WEB_BASE_URL` | the `web` service public URL | Post-login redirect target. |
| `AUTH_ALLOWED_EMAILS` | your email(s), comma-separated | Who may bootstrap a login (no public sign-up). |
| `COOKIE_SECURE` | `true` | Production is https. |
| `COOKIE_SAMESITE` | `lax` | The web proxy makes auth same-origin, so `lax` works (and is more robust than `none`). |
| `RESEND_API_KEY` | Resend API key | Without it the api falls back to logging emails instead of sending. |
| `EMAIL_FROM` | sender on a verified domain | e.g. `Health Agent <login@yourdomain>`. |
| `ENCRYPTION_KEY` | Fernet key | Encrypts stored OAuth tokens. Generate your own; do not ship the dev default. |
| `WHOOP_CLIENT_ID` / `WHOOP_CLIENT_SECRET` | from your Whoop dev app | OAuth + token refresh + webhook signature. |
| `WHOOP_REDIRECT_URI` | `https://<api>/v1/whoop/callback` | Must match the Whoop dev app exactly. |
| `WHOOP_API_BASE` | `https://api.prod.whoop.com` | Default; override only for testing. |
| `ANTHROPIC_API_KEY` | Anthropic key | Coach (chat + briefings). Without it, a deterministic stub is used. |
| `COACH_MODEL` | `claude-haiku-4-5` | Optional; daily coach + briefing model. |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` | from Cloudflare R2 | Meal-photo storage. All four required; otherwise meal upload falls back to an in-memory stub (dev only). |

> **Same-origin auth:** the web app proxies `/api/*` to this service (apps/web
> next.config.ts), so the browser only ever talks to the web origin and the session
> cookie is first-party. This avoids the third-party-cookie blocking that browsers now do
> by default. `API_BASE_URL` therefore points at the web `/api` path, not this service
> directly.

## Verify after deploy

- `GET /healthz` returns `200 {"status":"ok"}` from the public URL.
- `GET /db-ping` returns `200 {"status":"ok","result":1}` (proves the DB round-trip).
- After migrations have run (see worker), the magic-link login flow completes end to end.
