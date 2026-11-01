"""Read-only views over the ledger."""
from __future__ import annotations

import uuid

import asyncpg

from app.db import ledger


async def transaction(con, tx_id: str) -> tuple[asyncpg.Record | None, list[asyncpg.Record]]:
    try:
        parsed = uuid.UUID(tx_id)
    except ValueError:
        return None, []
    tx = await con.fetchrow("SELECT * FROM transactions WHERE id = $1", parsed)
    if not tx:
        return None, []
    entries = await con.fetch(
        "SELECT a.code, e.amount, e.balance_after FROM ledger_entries e JOIN accounts a ON a.id = e.account_id "
        "WHERE e.transaction_id = $1 ORDER BY e.id",
        parsed,
    )
    return tx, entries


async def user_entries(con, user_id: int, limit: int = 30) -> list[asyncpg.Record]:
    return await con.fetch(
        "SELECT t.id, t.kind, t.created_at, e.amount, e.balance_after "
        "FROM ledger_entries e JOIN transactions t ON t.id = e.transaction_id "
        "JOIN accounts a ON a.id = e.account_id WHERE a.code = $1 ORDER BY e.id DESC LIMIT $2",
        ledger.user_code(user_id), limit,
    )


async def transfer_summary(con, user_id: int) -> dict:
    code = ledger.user_code(user_id)
    row = await con.fetchrow(
        """SELECT COALESCE(SUM(e.amount) FILTER (WHERE e.amount > 0), 0) AS income,
                  COALESCE(-SUM(e.amount) FILTER (WHERE e.amount < 0), 0) AS outcome
             FROM ledger_entries e
             JOIN accounts a ON a.id = e.account_id
             JOIN transactions t ON t.id = e.transaction_id
            WHERE a.code = $1 AND t.kind = 'transfer'""",
        code,
    )
    incoming = await con.fetch(
        "SELECT t.id FROM ledger_entries e JOIN accounts a ON a.id = e.account_id "
        "JOIN transactions t ON t.id = e.transaction_id WHERE a.code = $1 AND t.kind = 'transfer' "
        "AND e.amount > 0 ORDER BY e.id DESC LIMIT 15", code)
    outgoing = await con.fetch(
        "SELECT t.id FROM ledger_entries e JOIN accounts a ON a.id = e.account_id "
        "JOIN transactions t ON t.id = e.transaction_id WHERE a.code = $1 AND t.kind = 'transfer' "
        "AND e.amount < 0 ORDER BY e.id DESC LIMIT 15", code)
    return {
        "income": row["income"],
        "outcome": row["outcome"],
        "incoming": [r["id"] for r in incoming],
        "outgoing": [r["id"] for r in outgoing],
    }
