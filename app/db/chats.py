"""Chats, membership and per-day activity."""
from __future__ import annotations

from datetime import date

import asyncpg

from app import constants


async def track(con, chat, user_id: int | None, registered: bool) -> None:
    """Remember a chat, the user's membership and bump the activity counter."""
    title = chat.title or " ".join(x for x in (chat.first_name, chat.last_name) if x) or None
    await con.execute(
        "INSERT INTO chats (id, type, title) VALUES ($1, $2, $3) "
        "ON CONFLICT (id) DO UPDATE SET last_seen = now(), type = EXCLUDED.type, title = EXCLUDED.title",
        chat.id, str(getattr(chat.type, "value", chat.type)), title,
    )
    if chat.id < 0 and user_id is not None:
        if registered:
            await con.execute(
                "INSERT INTO user_chats (user_id, chat_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                user_id, chat.id,
            )
        await con.execute(
            "INSERT INTO chat_activity (chat_id, day, user_id, messages) "
            "VALUES ($1, (now() AT TIME ZONE $3)::date, $2, 1) "
            "ON CONFLICT (chat_id, day, user_id) DO UPDATE SET messages = chat_activity.messages + 1",
            chat.id, user_id, constants.TZ_NAME,
        )


async def add_member(con, user_id: int, chat_id: int) -> None:
    await con.execute(
        "INSERT INTO user_chats (user_id, chat_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        user_id, chat_id,
    )


async def remove_member(con, user_id: int, chat_id: int) -> bool:
    result = await con.execute(
        "DELETE FROM user_chats WHERE user_id = $1 AND chat_id = $2", user_id, chat_id
    )
    return result.endswith("1")


async def all_chat_ids(con) -> list[int]:
    return [r["id"] for r in await con.fetch("SELECT id FROM chats ORDER BY id")]


async def member_names(con, chat_id: int) -> list[asyncpg.Record]:
    return await con.fetch(
        "SELECT u.id, u.name FROM users u JOIN user_chats uc ON uc.user_id = u.id "
        "WHERE uc.chat_id = $1 AND NOT u.is_deleted",
        chat_id,
    )


async def activity_today(con, chat_id: int) -> dict[int, int]:
    rows = await con.fetch(
        "SELECT user_id, messages FROM chat_activity "
        "WHERE chat_id = $1 AND day = (now() AT TIME ZONE $2)::date",
        chat_id, constants.TZ_NAME,
    )
    return {r["user_id"]: r["messages"] for r in rows}


async def activity_by_day(con, chat_id: int, days: int = 14) -> list[tuple[date, int]]:
    rows = await con.fetch(
        "SELECT g.day::date AS day, COALESCE(SUM(a.messages), 0)::int AS total "
        "FROM generate_series(((now() AT TIME ZONE $3)::date - ($2::int - 1))::timestamp, "
        "                     (now() AT TIME ZONE $3)::date::timestamp, interval '1 day') AS g(day) "
        "LEFT JOIN chat_activity a ON a.chat_id = $1 AND a.day = g.day::date "
        "GROUP BY g.day ORDER BY g.day",
        chat_id, days, constants.TZ_NAME,
    )
    return [(r["day"], r["total"]) for r in rows]
