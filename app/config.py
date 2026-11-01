"""Runtime settings loaded from the environment / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    token: str
    dsn: str
    owner_ids: frozenset[int]
    bot_username: str
    log_level: str
    log_dir: Path


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("TOKEN", "").strip()
    dsn = os.getenv("DATABASE_DSN", "").strip()
    if not token:
        raise ConfigError("TOKEN is not set. Put the bot API token into the .env file.")
    if not dsn:
        raise ConfigError("DATABASE_DSN is not set. Put the PostgreSQL DSN into the .env file.")
    owners_raw = os.getenv("OWNER_IDS", "")
    try:
        owners = frozenset(int(x) for x in owners_raw.replace(";", ",").split(",") if x.strip())
    except ValueError as exc:
        raise ConfigError("OWNER_IDS must be a comma separated list of integers.") from exc
    return Settings(
        token=token,
        dsn=dsn,
        owner_ids=owners,
        bot_username=os.getenv("BOT_USERNAME", "").strip().lstrip("@"),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        log_dir=Path(os.getenv("LOG_DIR", "logs")),
    )
