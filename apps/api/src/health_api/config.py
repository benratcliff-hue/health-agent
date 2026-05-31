"""Runtime configuration, read from the environment (and a local .env in dev)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Optional so the service can boot (and answer /healthz) even before a database is
    # wired up. /db-ping fails loudly when it is missing.
    database_url: str | None = None

    # Comma-separated browser origins allowed to call the API. Kept as a plain string
    # (split at use) to sidestep pydantic-settings' JSON-only parsing of list-typed env
    # vars. Defaults to the local Next.js dev server.
    cors_allow_origins: str = "http://localhost:3000"

    log_level: str = "INFO"

    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]
