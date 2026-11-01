"""Single-use confirmation buttons (pay, dice, casino warning, ...)."""
from __future__ import annotations

import uuid

import asyncpg

from app import constants


async def create(con, kind: str, owner_id: int, payload: dict, chat_id: int | None = None) -> str:
    action_id = await con.fetchval(
        "INSERT INTO pending_actions (kind, owner_id, chat_id, payload) VALUES ($1, $2, $3, $4) RETURNING id",
        kind, owner_id, chat_id, payload,
    )
    return action_id.hex


def _parse(action_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(action_id)
    except ValueError:
        return None


async def peek(con, action_id: str) -> asyncpg.Record | None:
    parsed = _parse(action_id)
    if parsed is None:
        return None
    return await con.fetchrow(
        "SELECT * FROM pending_actions WHERE id = $1 AND created_at > now() - make_interval(secs => $2)",
        parsed, float(constants.ACTION_TTL),
    )


async def take(con, action_id: str) -> asyncpg.Record | None:
    """Atomically consume an action (guarantees a button works only once)."""
    parsed = _parse(action_id)
    if parsed is None:
        return None
    return await con.fetchrow(
        "DELETE FROM pending_actions WHERE id = $1 AND created_at > now() - make_interval(secs => $2) "
        "RETURNING *",
        parsed, float(constants.ACTION_TTL),
    )


async def purge(con) -> int:
    result = await con.execute(
        "DELETE FROM pending_actions WHERE created_at < now() - make_interval(secs => $1)",
        float(constants.ACTION_TTL),
    )
    return int(result.split()[-1])
