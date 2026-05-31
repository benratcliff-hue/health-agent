# Railway service: postgres

Managed Postgres. Add via Railway's "New > Database > PostgreSQL".

- **Build command:** none (managed).
- **Run command:** none (managed).
- **Provides:** a `DATABASE_URL` connection string, referenced by `api` and `worker`.
- **Backups:** enable Railway's daily backups (PRD section 11.4).

Nothing to deploy from this repo; it exists so the other services have a database.
