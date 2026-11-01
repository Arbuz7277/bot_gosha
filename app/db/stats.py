"""Rankings, key-value storage and statistics."""
from __future__ import annotations

import asyncpg

_EFFECTIVE = "CASE WHEN u.hide_balance THEN 0 ELSE a.balance END"


async def chat_top(con, chat_id: int) -> list[asyncpg.Record]:
    return await con.fetch(
        f"""SELECT u.id, u.name, u.username, {_EFFECTIVE} AS bal,
                   ROW_NUMBER() OVER (ORDER BY {_EFFECTIVE} DESC, u.id) AS pos
              FROM users u
              JOIN accounts a ON a.id = u.account_id
              JOIN user_chats uc ON uc.user_id = u.id AND uc.chat_id = $1
             WHERE NOT u.is_deleted AND NOT u.hide_top
             ORDER BY pos""",
        chat_id,
    )


async def global_top(con, limit: int) -> tuple[list[asyncpg.Record], int]:
    rows = await con.fetch(
        f"""SELECT u.id, u.name, u.username, {_EFFECTIVE} AS bal,
                   ROW_NUMBER() OVER (ORDER BY {_EFFECTIVE} DESC, u.id) AS pos
              FROM users u JOIN accounts a ON a.id = u.account_id
             WHERE NOT u.is_deleted AND NOT u.hide_top
             ORDER BY pos LIMIT $1""",
        limit,
    )
    total = await con.fetchval("SELECT count(*) FROM users WHERE NOT is_deleted AND NOT hide_top")
    return rows, total


async def global_position(con, user_id: int) -> int | None:
    return await con.fetchval(
        f"""SELECT pos FROM (
                SELECT u.id, ROW_NUMBER() OVER (ORDER BY {_EFFECTIVE} DESC, u.id) AS pos
                  FROM users u JOIN accounts a ON a.id = u.account_id
                 WHERE NOT u.is_deleted AND NOT u.hide_top) t
            WHERE id = $1""",
        user_id,
    )


async def users_money(con) -> tuple:
    row = await con.fetchrow(
        "SELECT COALESCE(SUM(a.balance), 0) AS total, count(*) AS n "
        "FROM users u JOIN accounts a ON a.id = u.account_id WHERE NOT u.is_deleted"
    )
    return row["total"], row["n"]


async def snapshot(con) -> None:
    total, n = await users_money(con)
    await con.execute("INSERT INTO balance_snapshots (total, users_count) VALUES ($1, $2)", total, n)


async def snapshots(con, limit: int = 24 * 14) -> list[asyncpg.Record]:
    rows = await con.fetch("SELECT taken_at, total, users_count FROM balance_snapshots ORDER BY taken_at DESC LIMIT $1", limit)
    return list(reversed(rows))


async def kv_get(con, key: str, default=None):
    value = await con.fetchval("SELECT value FROM kv WHERE key = $1", key)
    return default if value is None else value


async def kv_set(con, key: str, value) -> None:
    await con.execute(
        "INSERT INTO kv (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        key, value,
    )
