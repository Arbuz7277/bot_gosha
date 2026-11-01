"""Anonymous feedback to the owners."""
from __future__ import annotations

import asyncpg

from app import constants


async def cooldown_left(con, user_id: int) -> float:
    left = await con.fetchval(
        "SELECT GREATEST(0, $2 - EXTRACT(EPOCH FROM now() - max(created_at)))::float "
        "FROM feedback_messages WHERE user_id = $1",
        user_id, float(constants.KD_FEEDBACK),
    )
    return left or 0.0


async def start(con, user_id: int) -> None:
    await con.execute(
        "INSERT INTO feedback_pending (user_id) VALUES ($1) ON CONFLICT (user_id) DO UPDATE SET created_at = now()",
        user_id,
    )


async def is_pending(con, user_id: int) -> bool:
    return bool(await con.fetchval("SELECT 1 FROM feedback_pending WHERE user_id = $1", user_id))


async def cancel(con, user_id: int) -> bool:
    result = await con.execute("DELETE FROM feedback_pending WHERE user_id = $1", user_id)
    return result.endswith("1")


async def submit(con, user_id: int, text: str) -> int | None:
    async with con.transaction():
        deleted = await con.execute("DELETE FROM feedback_pending WHERE user_id = $1", user_id)
        if not deleted.endswith("1"):
            return None
        return await con.fetchval(
            "INSERT INTO feedback_messages (user_id, text) VALUES ($1, $2) RETURNING id", user_id, text
        )


async def get(con, feedback_id: int) -> asyncpg.Record | None:
    return await con.fetchrow("SELECT * FROM feedback_messages WHERE id = $1", feedback_id)


async def mark_answered(con, feedback_id: int) -> None:
    await con.execute("UPDATE feedback_messages SET answered_at = now() WHERE id = $1", feedback_id)
