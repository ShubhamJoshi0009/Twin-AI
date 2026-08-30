"""Application configuration using pydantic-settings."""

from __future__ import annotations

import json
import logging
import secrets
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ruff: noqa: UP006, UP035 — keep `typing.List` for Python 3.9 compat.

_DEFAULT_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "Business Twin AI"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    # Debug mode: enables SQL echo, verbose logging, Swagger docs, etc.
    # Must be false in production.
    APP_DEBUG: bool = False

    # ── Demo data ─────────────────────────────────────────
    # Seed the DB with a demo dataset on first startup (only when empty).
    AUTO_SEED_DEMO: bool = True
    # Enable the seeding API (Settings → Data & Seeding). It is destructive
    # when `force=true` — keep it OFF in production (default).
    ENABLE_SEED_API: bool = False
    # Optional path to a custom JSON data file — lets users seed the platform
    # with their own business / supply chain profile instead of the demo data.
    # See demo_data.example.json in the repo root for the format.
    CUSTOM_DATA_FILE: str = ""

    # ── Database ─────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/business_twin_ai"

    # ── LLM ──────────────────────────────────────────────
    LLM_PROVIDER: str = "openai"  # "openai" | "gemini"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000

    # ── News API ──────────────────────────────────────────
    # Optional keyed news provider (NewsAPI.org) used ahead of the free GDELT
    # feed. When NEWS_API_KEY is set, headline lookups prefer NewsAPI.org and
    # transparently fall back to GDELT → curated pool when it fails / rate-limits.
    NEWS_API_KEY: str = ""

    # ── Weather (supply-route monitoring) ─────────────────
    # Free Open-Meteo endpoint — no API key required (mirrors the GDELT
    # pattern). Set WEATHER_API_KEY to point at the commercial endpoint when
    # you need higher rate limits / an SLA. The service always falls back to
    # deterministic simulated conditions when the provider is unreachable, so
    # the route-weather UI never goes empty.
    WEATHER_API_URL: str = "https://api.open-meteo.com/v1/forecast"
    WEATHER_API_KEY: str = ""
    # How long in-memory per-coordinate weather is considered fresh.
    WEATHER_CACHE_TTL_SECONDS: int = 5 * 60
    # Force the simulated provider (offline demos / deterministic tests).
    WEATHER_FORCE_SIMULATED: bool = False

    # ── Security ─────────────────────────────────────────
    # Used to sign session cookies / tokens. Overridden with a random value
    # at runtime when left at the placeholder, but you SHOULD set a real one
    # in production so restarts keep stable signatures.
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    # JSON list of allowed browser origins (the frontend URL(s)).
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:3001"]'
    # Comma-separated list of allowed Host headers, e.g. "api.example.com".
    # Empty = allow any host (dev only). Set in production.
    TRUSTED_HOSTS: str = ""

    # ── Reports ──────────────────────────────────────────
    REPORT_OUTPUT_DIR: str = "./reports"

    # ── Profile source checklist ─────────────────────────
    # How often the background task re-audits every profile's source checklist
    # and logs coverage regressions. 0 disables the scheduled auto-verify
    # (manual re-audits via POST /digital-twins/sources/refresh still work).
    PROFILE_AUDIT_INTERVAL_SECONDS: int = 86400

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def _validate_secret_key(cls, value: str) -> str:
        """Replace the placeholder with a random secret unless explicitly set.

        Note: pydantic-settings treats an *unset* env var the same as the
        default, so this fires when the user left SECRET_KEY unset. A real
        production secret should be provided explicitly via env.
        """
        if value == _DEFAULT_SECRET_KEY:
            generated = secrets.token_urlsafe(48)
            logger.warning(
                "SECRET_KEY is not set — generated a random one for this process. "
                "Set SECRET_KEY explicitly in production so sessions survive restarts."
            )
            return generated
        return value

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS JSON string into a list."""
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:3000"]

    @property
    def trusted_hosts_list(self) -> List[str]:
        """Parse TRUSTED_HOSTS comma-separated string into a list."""
        return [h.strip() for h in self.TRUSTED_HOSTS.split(",") if h.strip()]


settings = Settings()
