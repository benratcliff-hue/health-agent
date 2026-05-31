# Railway service: web

Next.js web app (`apps/web`).

- **Root directory:** `apps/web` (self-contained; no workspace dependency).
- **Build / start commands:** none needed. Railpack auto-detects Next.js and builds and
  starts it; `next start` binds to `$PORT`. Override only if that ever stops working
  (`npm ci && npm run build` / `npm run start -- --port $PORT`).

## Environment variables

| Variable | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | the `api` service public URL | Inlined at **build** time; must be set before the build runs. |

## Verify after deploy

- The public URL renders the M0 status page with green checks for both
  `/healthz` and `/db-ping`, proving web -> api -> Postgres end to end.
