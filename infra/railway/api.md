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
| `DATABASE_URL` | reference from `postgres` | Used by `/db-ping`. |
| `CORS_ALLOW_ORIGINS` | the `web` service public URL | Comma-separated; lets the browser call the api. |
| `LOG_LEVEL` | `INFO` | Optional. |

## Verify after deploy

- `GET /healthz` returns `200 {"status":"ok"}` from the public URL.
- `GET /db-ping` returns `200 {"status":"ok","result":1}` (proves the DB round-trip).
