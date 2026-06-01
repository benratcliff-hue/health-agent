# Railway service: web

Next.js web app (`apps/web`).

- **Root directory:** `apps/web` (self-contained; no workspace dependency).
- **Build / start commands:** none needed. Railpack auto-detects Next.js and builds and
  starts it; `next start` binds to `$PORT`. Override only if that ever stops working
  (`npm ci && npm run build` / `npm run start -- --port $PORT`).

## Environment variables

| Variable | Value | Notes |
|---|---|---|
| `API_ORIGIN` | the `api` service public URL | The web app proxies `/api/*` to it (next.config.ts) so browser auth calls stay same-origin and the session cookie is first-party. Read at runtime. |

## Verify after deploy

- The public URL renders the M0 status page with green checks for both
  `/healthz` and `/db-ping`, proving web -> api -> Postgres end to end.
