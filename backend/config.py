"""
Single source of truth for every externally-configurable value.

Nothing in this codebase should read os.getenv directly or hardcode a host —
add it here instead. Defaults are the local docker-compose setup, so the app
runs with zero environment variables set; every deployment target is then just
a different set of env vars, with no code change.
"""

from __future__ import annotations

import os


def _env(name: str, default: str) -> str:
    """Read an env var, treating empty/whitespace as unset."""
    return (os.getenv(name) or "").strip() or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


# ── Database ──────────────────────────────────────────────────────────────────
# Accepts postgres://, postgresql:// or postgresql+asyncpg:// — normalised below.
DATABASE_URL = _env(
    "DATABASE_URL",
    "postgresql+asyncpg://datachecker:datachecker@localhost:5432/datachecker",
)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Seconds to wait for a TCP connection to Postgres before giving up. Without
# this a dead database makes every request hang forever instead of erroring.
DB_CONNECT_TIMEOUT = _env_int("DB_CONNECT_TIMEOUT", 10)
DB_COMMAND_TIMEOUT = _env_int("DB_COMMAND_TIMEOUT", 30)
# How long startup may spend creating tables before the app boots anyway.
DB_INIT_TIMEOUT = _env_int("DB_INIT_TIMEOUT", 15)


# ── Upstream data portal ──────────────────────────────────────────────────────
# Point this at a Saudi-IP relay when the host running this app is outside KSA;
# the portal's WAF rejects non-Saudi source IPs. Path layout is identical either
# way, so only this value changes.
PORTAL_BASE_URL = _env("PORTAL_BASE_URL", "https://open.data.gov.sa").rstrip("/")
PORTAL_API_BASE = f"{PORTAL_BASE_URL}/data/api"

# Shared secret sent as x-relay-key when talking to a relay. Empty = no relay.
RELAY_KEY = _env("RELAY_KEY", "")

HTTP_TIMEOUT = _env_int("HTTP_TIMEOUT", 30)


# ── HTTP / CORS ───────────────────────────────────────────────────────────────
# Comma-separated origin list, or "*" for any. Tighten this once the frontend
# has a stable domain.
CORS_ORIGINS = [o.strip() for o in _env("CORS_ORIGINS", "*").split(",") if o.strip()]


# ── Feature gates ─────────────────────────────────────────────────────────────
# Bulk and seed endpoints fan out into many upstream requests, so they stay off
# by default and must be explicitly enabled for admin/seeding runs.
ENABLE_BULK_ENDPOINTS = _env_bool("ENABLE_BULK_ENDPOINTS", False)
