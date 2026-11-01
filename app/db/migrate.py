"""Tiny SQL migration runner (files in ./migrations, applied in name order)."""
from __future__ import annotations

import logging
import secrets
from pathlib import Path

import asyncpg

from app import constants
from app.db import ledger

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
ADVISORY_LOCK_ID = 727_001


async def run_migrations(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as con:
        await con.execute("SELECT pg_advisory_lock($1)", ADVISORY_LOCK_ID)
        try:
            await con.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            applied = {r["version"] for r in await con.fetch("SELECT version FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name in applied:
                    continue
                logger.info("Applying migration %s", path.name)
                async with con.transaction():
                    await con.execute(path.read_text(encoding="utf-8"))
                    await con.execute("INSERT INTO schema_migrations (version) VALUES ($1)", path.name)
            await _seed(con)
        finally:
            await con.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_ID)
    logger.info("Database schema is up to date")


async def _seed(con: asyncpg.Connection) -> None:
    await ledger.ensure_system_accounts(con)
    await ledger.ensure_genesis(con, constants.GENESIS_BANK)
    await con.execute(
        "INSERT INTO mining_state (id, seed, target_hex) VALUES (1, $1, $2) ON CONFLICT (id) DO NOTHING",
        secrets.token_bytes(32).hex(),
        f"{constants.MINE_MAX_TARGET:064x}",
    )
    await con.execute(
        "INSERT INTO kv (key, value) VALUES ('number_target', to_jsonb($1::int)) ON CONFLICT (key) DO NOTHING",
        secrets.randbelow(constants.NUMBER_MAX) + 1,
    )
