"""User repository."""
from __future__ import annotations

import logging
from typing import Any

import asyncpg

from app.db import ledger

logger = logging.getLogger(__name__)

_SELECT = (
    "SELECT u.*, a.balance FROM users u JOIN accounts a ON a.id = u.account_id "
)

# Columns that may be toggled from the settings menu.
SETTING_COLUMNS = {
    "transfer_check", "hide_username", "hide_balance", "hide_top", "casino_warning",
}


async def get(con, user_id: int) -> asyncpg.Record | None:
    return await con.fetchrow(_SELECT + "WHERE u.id = $1 AND NOT u.is_deleted", user_id)


async def get_by_gid(con, gid: int) -> asyncpg.Record | None:
    return await con.fetchrow(_SELECT + "WHERE u.gid = $1 AND NOT u.is_deleted", gid)


async def get_by_username(con, username: str) -> asyncpg.Record | None:
    return await con.fetchrow(
        _SELECT + "WHERE lower(u.username) = lower($1) AND NOT u.is_deleted", username.lstrip("@")
    )


async def find(con, token: str) -> asyncpg.Record | None:
    """Find a user by @username, Telegram id or Gosha id."""
    token = token.strip()
    if not token:
        return None
    if token.lstrip("@").isdigit() and not token.startswith("@"):
        number = int(token)
        if number < 2 ** 63:
            found = await get(con, number) or await get_by_gid(con, number)
            if found:
                return found
        return None
    return await get_by_username(con, token)


async def _release_username(con, user_id: int, username: str | None) -> None:
    if username:
        await con.execute(
            "UPDATE users SET username = NULL WHERE lower(username) = lower($1) AND id <> $2",
            username,
            user_id,
        )


async def register(con, user_id: int, name: str, username: str | None) -> tuple[asyncpg.Record, bool]:
    """Create (or revive) a user. Returns (user, created)."""
    async with con.transaction():
        account_id = await con.fetchval(
            "INSERT INTO accounts (code, kind) VALUES ($1, 'user') "
            "ON CONFLICT (code) DO UPDATE SET code = EXCLUDED.code RETURNING id",
            ledger.user_code(user_id),
        )
        existing = await con.fetchrow("SELECT is_deleted FROM users WHERE id = $1 FOR UPDATE", user_id)
        if existing and not existing["is_deleted"]:
            return await get(con, user_id), False
        await _release_username(con, user_id, username)
        if existing:
            await con.execute(
                """UPDATE users SET is_deleted = FALSE, name = $2, username = $3,
                          registered_at = now(), last_farm_at = NULL, is_admin = FALSE,
                          transfer_check = TRUE, hide_username = TRUE, hide_balance = FALSE,
                          hide_top = FALSE, casino_warning = TRUE
                    WHERE id = $1""",
                user_id, name, username,
            )
        else:
            await con.execute(
                "INSERT INTO users (id, account_id, name, username) VALUES ($1, $2, $3, $4)",
                user_id, account_id, name, username,
            )
        logger.info("Registered user %s", user_id)
        return await get(con, user_id), True


async def sync_username(con, user_id: int, username: str | None) -> None:
    async with con.transaction():
        await _release_username(con, user_id, username)
        await con.execute(
            "UPDATE users SET username = $2 WHERE id = $1 AND username IS DISTINCT FROM $2",
            user_id, username,
        )


async def set_name(con, user_id: int, name: str) -> None:
    await con.execute("UPDATE users SET name = $2 WHERE id = $1", user_id, name)


async def set_setting(con, user_id: int, column: str, value: bool) -> None:
    if column not in SETTING_COLUMNS:
        raise ValueError(f"unknown setting {column}")
    await con.execute(f"UPDATE users SET {column} = $2 WHERE id = $1", user_id, value)  # noqa: S608


async def set_admin(con, user_id: int, value: bool) -> None:
    await con.execute("UPDATE users SET is_admin = $2 WHERE id = $1", user_id, value)


async def count(con) -> int:
    return await con.fetchval("SELECT count(*) FROM users WHERE NOT is_deleted")


async def admin_ids(con) -> list[int]:
    rows = await con.fetch("SELECT id FROM users WHERE is_admin AND NOT is_deleted")
    return [r["id"] for r in rows]


async def delete_account(con, user_id: int) -> None:
    """Soft-delete a user; the remaining balance goes back to the bank."""
    from app.db import borrow  # local import to avoid a cycle

    async with con.transaction():
        if await borrow.has_active_loans(con, user_id):
            raise ValueError("active loans")
        user = await con.fetchrow(_SELECT + "WHERE u.id = $1 AND NOT u.is_deleted FOR UPDATE OF u", user_id)
        if not user:
            return
        code = ledger.user_code(user_id)
        bal = await ledger.balance(con, code)
        if bal > 0:
            await ledger.post(con, "account_deleted", {code: -bal, ledger.BANK: bal}, initiator_id=user_id)
        elif bal < 0:
            await ledger.post(con, "account_deleted", {code: -bal, ledger.EMISSION: bal}, initiator_id=user_id)
        await con.execute("DELETE FROM user_chats WHERE user_id = $1", user_id)
        await con.execute("DELETE FROM pending_actions WHERE owner_id = $1", user_id)
        await con.execute("DELETE FROM feedback_pending WHERE user_id = $1", user_id)
        await con.execute(
            "UPDATE borrow_requests SET status = 'cancelled', settled_at = now() "
            "WHERE status = 'pending' AND (borrower_id = $1 OR lender_id = $1)",
            user_id,
        )
        await con.execute(
            "UPDATE users SET is_deleted = TRUE, username = NULL, name = 'deleted', is_admin = FALSE "
            "WHERE id = $1",
            user_id,
        )
    logger.info("Account %s deleted", user_id)


def as_dict(record: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(record) if record else None
