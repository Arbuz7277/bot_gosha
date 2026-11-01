"""Double-entry ledger.

* ``ledger_entries`` is the single source of truth for money.
* every call to :func:`post` writes ONE transaction whose entries sum to zero
  (also enforced by a deferred constraint trigger in the database);
* ``accounts.balance`` is a cache that is updated in the same DB transaction
  and can be rebuilt with :func:`reconcile`.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping

import asyncpg

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

BANK = "bank"
EMISSION = "emission"          # source/sink of coins created or destroyed by the game
JACKPOT = "jackpot"
NUMBER_POT = "number_pot"
ROULETTE_ESCROW = "roulette_escrow"

# code -> allow_negative
SYSTEM_ACCOUNTS: dict[str, bool] = {
    BANK: False,
    EMISSION: True,
    JACKPOT: False,
    NUMBER_POT: False,
    ROULETTE_ESCROW: False,
}


class LedgerError(Exception):
    """Invalid ledger operation."""


class InsufficientFunds(LedgerError):
    def __init__(self, account: str, needed: Decimal, available: Decimal) -> None:
        super().__init__(f"insufficient funds on {account}: need {needed}, have {available}")
        self.account = account
        self.needed = needed
        self.available = available


def user_code(user_id: int) -> str:
    return f"user:{user_id}"


def q(value: Decimal | int | str) -> Decimal:
    """Quantize to cents (half-up)."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


async def ensure_system_accounts(con: asyncpg.Connection) -> None:
    for code, allow_negative in SYSTEM_ACCOUNTS.items():
        await con.execute(
            "INSERT INTO accounts (code, kind, allow_negative) VALUES ($1, 'system', $2) "
            "ON CONFLICT (code) DO NOTHING",
            code,
            allow_negative,
        )


async def balance(con: asyncpg.Connection | asyncpg.Pool, code: str) -> Decimal:
    value = await con.fetchval("SELECT balance FROM accounts WHERE code = $1", code)
    if value is None:
        raise LedgerError(f"unknown account {code}")
    return value


async def post(
    con: asyncpg.Connection,
    kind: str,
    legs: Mapping[str, Decimal] | Iterable[tuple[str, Decimal]],
    *,
    initiator_id: int | None = None,
    comment: str | None = None,
    meta: dict | None = None,
    overdraft: Iterable[str] = (),
) -> uuid.UUID:
    """Record one balanced transaction.

    ``legs`` maps account code -> signed amount. The amounts must sum to zero.
    Accounts listed in ``overdraft`` (and accounts flagged ``allow_negative``)
    may go below zero; every other account may not.
    """
    items = legs.items() if isinstance(legs, Mapping) else legs
    merged: dict[str, Decimal] = {}
    for code, amount in items:
        amount = Decimal(amount)
        if amount != q(amount):
            raise LedgerError(f"amount {amount} has more than 2 decimal places")
        merged[code] = merged.get(code, ZERO) + amount
    merged = {code: amount for code, amount in merged.items() if amount != 0}

    if len(merged) < 2:
        raise LedgerError("a transaction needs at least two non-zero legs")
    total = sum(merged.values(), ZERO)
    if total != 0:
        raise LedgerError(f"unbalanced transaction ({kind}): sum = {total}")

    overdraft_set = set(overdraft)
    tx_id = uuid.uuid4()
    async with con.transaction():
        # Lock accounts in a stable order to avoid deadlocks.
        rows = await con.fetch(
            "SELECT id, code, balance, allow_negative FROM accounts "
            "WHERE code = ANY($1::text[]) ORDER BY id FOR UPDATE",
            list(merged),
        )
        if len(rows) != len(merged):
            missing = set(merged) - {r["code"] for r in rows}
            raise LedgerError(f"unknown account(s): {', '.join(sorted(missing))}")

        entries = []
        updates = []
        for row in rows:
            amount = merged[row["code"]]
            new_balance = row["balance"] + amount
            if (
                amount < 0
                and new_balance < 0
                and not row["allow_negative"]
                and row["code"] not in overdraft_set
            ):
                raise InsufficientFunds(row["code"], -amount, row["balance"])
            entries.append((tx_id, row["id"], amount, new_balance))
            updates.append((row["id"], new_balance))

        await con.execute(
            "INSERT INTO transactions (id, kind, initiator_id, comment, meta) "
            "VALUES ($1, $2, $3, $4, $5)",
            tx_id,
            kind,
            initiator_id,
            comment,
            meta or {},
        )
        await con.executemany(
            "INSERT INTO ledger_entries (transaction_id, account_id, amount, balance_after) "
            "VALUES ($1, $2, $3, $4)",
            entries,
        )
        await con.executemany("UPDATE accounts SET balance = $2 WHERE id = $1", updates)

    logger.info(
        "Ledger tx %s kind=%s legs=%s",
        tx_id,
        kind,
        ", ".join(f"{c}:{a:+}" for c, a in sorted(merged.items())),
    )
    return tx_id


async def ensure_genesis(con: asyncpg.Connection, bank_amount: Decimal) -> None:
    """Mint the initial bank funding exactly once."""
    async with con.transaction():
        exists = await con.fetchval("SELECT 1 FROM transactions WHERE kind = 'genesis' LIMIT 1")
        if exists:
            return
        await post(
            con,
            "genesis",
            {EMISSION: -bank_amount, BANK: bank_amount},
            comment="Initial bank funding",
        )
        logger.info("Genesis transaction created: bank funded with %s", bank_amount)


async def reconcile(con: asyncpg.Connection, *, repair: bool = False) -> dict:
    """Compare cached balances with the ledger.

    Returns a report with mismatched accounts, unbalanced transactions and the
    global ledger sum (must be zero). With ``repair=True`` the cache is rebuilt.
    """
    mismatches = await con.fetch(
        """
        SELECT a.code, a.balance AS cached, COALESCE(s.total, 0) AS ledger
          FROM accounts a
          LEFT JOIN (SELECT account_id, SUM(amount) AS total
                       FROM ledger_entries GROUP BY account_id) s ON s.account_id = a.id
         WHERE a.balance <> COALESCE(s.total, 0)
        """
    )
    unbalanced = await con.fetch(
        "SELECT transaction_id, SUM(amount) AS total FROM ledger_entries "
        "GROUP BY transaction_id HAVING SUM(amount) <> 0"
    )
    total = await con.fetchval("SELECT COALESCE(SUM(amount), 0) FROM ledger_entries")
    if repair and mismatches:
        await con.execute(
            "UPDATE accounts a SET balance = COALESCE("
            "(SELECT SUM(amount) FROM ledger_entries e WHERE e.account_id = a.id), 0)"
        )
        logger.warning("Rebuilt %d cached balance(s) from the ledger", len(mismatches))
    return {
        "mismatches": [dict(r) for r in mismatches],
        "unbalanced": [dict(r) for r in unbalanced],
        "ledger_sum": total,
        "repaired": bool(repair and mismatches),
    }
