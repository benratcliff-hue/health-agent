"""Runtime configuration, read from the environment (and a local .env in dev)."""

from __future__ import annotations

import functools

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

    # --- Auth ---
    # Signs session JWTs. MUST be set to a strong random value in any deployed env; the
    # dev default exists only so localhost works out of the box.
    secret_key: str = "dev-insecure-change-me"
    # Public base URL of this api, used to build the magic-link URL in emails.
    api_base_url: str = "http://localhost:8000"
    # Where to send the user after a successful magic-link login.
    web_base_url: str = "http://localhost:3000"
    magic_link_ttl_minutes: int = 15
    session_ttl_days: int = 30
    # Cookie flags. Locally we serve over http, so Secure must be off and SameSite=lax.
    # In production (https, cross-site web<->api) set COOKIE_SECURE=true, COOKIE_SAMESITE=none.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_name: str = "ha_session"
    # Emails permitted to bootstrap a login (no public sign-up; PRD non-goal). Comma-separated.
    auth_allowed_emails: str = ""
    # Household created for the first bootstrapped user.
    household_name: str = "Household"

    # --- Encryption (M1) ---
    # Fernet key for encrypting stored OAuth tokens (PRD 11.2). The dev default is a real
    # but public key; generate your own for any deployed env:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = "AoiLqfVpiKqQOSx-rO57uKQwAdoAuxZK-FAGmFj1OSg="

    # --- Whoop (M1) ---
    whoop_client_id: str = ""
    whoop_client_secret: str = ""
    whoop_redirect_uri: str = "http://localhost:8000/v1/whoop/callback"
    whoop_api_base: str = "https://api.prod.whoop.com"

    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    def allowed_emails_set(self) -> set[str]:
        return {e.strip().lower() for e in self.auth_allowed_emails.split(",") if e.strip()}


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
