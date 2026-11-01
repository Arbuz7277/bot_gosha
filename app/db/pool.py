"""asyncpg pool factory."""
from __future__ import annotations

import json
import logging

import asyncpg

logger = logging.getLogger(__name__)


async def _init_connection(con: asyncpg.Connection) -> None:
    # JSONB <-> python objects
    await con.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await con.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def create_pool(dsn: str, *, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    logger.info("Connecting to PostgreSQL...")
    pool = await asyncpg.create_pool(
        dsn, min_size=min_size, max_size=max_size, init=_init_connection, command_timeout=30
    )
    version = await pool.fetchval("SHOW server_version")
    logger.info("Connected to PostgreSQL %s", version)
    return pool
