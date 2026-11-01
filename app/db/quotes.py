"""Quotes and votes."""
from __future__ import annotations

import asyncpg


async def add(con, author_id: int, author_name: str, text: str) -> int:
    return await con.fetchval(
        "INSERT INTO quotes (author_id, author_name, text) VALUES ($1, $2, $3) RETURNING id",
        author_id, author_name, text,
    )


async def get(con, quote_id: int) -> asyncpg.Record | None:
    return await con.fetchrow(
        """SELECT q.*, u.name AS current_name,
                  (SELECT count(*) FROM quote_votes v WHERE v.quote_id = q.id AND v.vote = 1)  AS likes,
                  (SELECT count(*) FROM quote_votes v WHERE v.quote_id = q.id AND v.vote = -1) AS dislikes
             FROM quotes q LEFT JOIN users u ON u.id = q.author_id AND NOT u.is_deleted
            WHERE q.id = $1""",
        quote_id,
    )


async def random_id(con) -> int | None:
    return await con.fetchval(
        "SELECT id FROM quotes WHERE verified IS DISTINCT FROM FALSE ORDER BY random() LIMIT 1"
    )


async def reported_ids(con) -> list[int]:
    return [r["id"] for r in await con.fetch("SELECT id FROM quotes WHERE verified = FALSE ORDER BY id")]


async def vote(con, quote_id: int, user_id: int, value: int) -> None:
    """Toggle a vote: pressing the same button again removes the vote."""
    async with con.transaction():
        current = await con.fetchval(
            "SELECT vote FROM quote_votes WHERE quote_id = $1 AND user_id = $2 FOR UPDATE", quote_id, user_id
        )
        if current == value:
            await con.execute("DELETE FROM quote_votes WHERE quote_id = $1 AND user_id = $2", quote_id, user_id)
        else:
            await con.execute(
                "INSERT INTO quote_votes (quote_id, user_id, vote) VALUES ($1, $2, $3) "
                "ON CONFLICT (quote_id, user_id) DO UPDATE SET vote = EXCLUDED.vote",
                quote_id, user_id, value,
            )


async def set_verified(con, quote_id: int, value: bool | None) -> bool:
    result = await con.execute("UPDATE quotes SET verified = $2 WHERE id = $1", quote_id, value)
    return result.endswith("1")


async def delete(con, quote_id: int) -> bool:
    result = await con.execute("DELETE FROM quotes WHERE id = $1", quote_id)
    return result.endswith("1")


async def user_quotes(con, user_id: int, page: int, per_page: int) -> tuple[list[asyncpg.Record], int]:
    total = await con.fetchval("SELECT count(*) FROM quotes WHERE author_id = $1", user_id)
    rows = await con.fetch(
        "SELECT id, text, created_at FROM quotes WHERE author_id = $1 ORDER BY id LIMIT $2 OFFSET $3",
        user_id, per_page, (page - 1) * per_page,
    )
    return rows, total
