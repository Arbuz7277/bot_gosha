"""Roulette bets (stakes are held in the roulette escrow account)."""
from __future__ import annotations

from decimal import Decimal

import asyncpg

from app.db import ledger


async def place_bet(
    con, chat_id: int, user_id: int, amount: Decimal, bet_type: str, multiplier: int
) -> tuple[int, str] | None:
    """Move the stake into escrow and record the bet.

    Returns (bet_id, tx_id) or None when the bank could not cover the potential win.
    """
    async with con.transaction():
        # Serialise bet placement so the solvency check below is race free.
        await con.execute("SELECT pg_advisory_xact_lock(727002)")
        bank = await ledger.balance(con, ledger.BANK)
        open_profit = await con.fetchval(
            "SELECT COALESCE(SUM(amount * (multiplier - 1)), 0) FROM roulette_bets"
        )
        if bank < open_profit + amount * (multiplier - 1):
            return None
        tx_id = await ledger.post(
            con,
            "roulette_bet",
            {ledger.user_code(user_id): -amount, ledger.ROULETTE_ESCROW: amount},
            initiator_id=user_id,
            meta={"chat_id": chat_id, "bet": bet_type},
        )
        bet_id = await con.fetchval(
            "INSERT INTO roulette_bets (chat_id, user_id, amount, bet_type, multiplier, stake_tx) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            chat_id, user_id, amount, bet_type, multiplier, tx_id,
        )
        return bet_id, str(tx_id)


async def user_bets(con, chat_id: int, user_id: int) -> list[asyncpg.Record]:
    return await con.fetch(
        "SELECT * FROM roulette_bets WHERE chat_id = $1 AND user_id = $2 ORDER BY id", chat_id, user_id
    )


async def first_bet_age(con, chat_id: int) -> float | None:
    """Seconds since the first open bet of the chat."""
    return await con.fetchval(
        "SELECT EXTRACT(EPOCH FROM now() - min(created_at))::float FROM roulette_bets WHERE chat_id = $1",
        chat_id,
    )


async def cancel_user_bets(con, chat_id: int, user_id: int) -> Decimal:
    """Refund every open bet of the user in the chat. Returns the refunded amount."""
    async with con.transaction():
        rows = await con.fetch(
            "DELETE FROM roulette_bets WHERE chat_id = $1 AND user_id = $2 RETURNING amount", chat_id, user_id
        )
        total = sum((r["amount"] for r in rows), Decimal("0.00"))
        if total > 0:
            await ledger.post(
                con,
                "roulette_cancel",
                {ledger.ROULETTE_ESCROW: -total, ledger.user_code(user_id): total},
                initiator_id=user_id,
                meta={"chat_id": chat_id},
            )
        return total


async def spin(con, chat_id: int, number: int, color: str) -> dict:
    """Settle all open bets of a chat atomically.

    Returns {"winners": [(user_id, payout)], "refunded": bool}.
    """
    async with con.transaction():
        await con.execute("SELECT pg_advisory_xact_lock(727002)")
        bets = await con.fetch("SELECT * FROM roulette_bets WHERE chat_id = $1 ORDER BY id FOR UPDATE", chat_id)
        if not bets:
            return {"winners": [], "refunded": False, "empty": True}

        stake_total = sum((b["amount"] for b in bets), Decimal("0.00"))
        legs: dict[str, Decimal] = {ledger.ROULETTE_ESCROW: -stake_total}
        payouts: dict[int, Decimal] = {}
        bank_delta = Decimal("0.00")
        for bet in bets:
            won = bet["bet_type"] == color or bet["bet_type"] == str(number)
            if won:
                payout = bet["amount"] * bet["multiplier"]
                payouts[bet["user_id"]] = payouts.get(bet["user_id"], Decimal("0.00")) + payout
                bank_delta -= bet["amount"] * (bet["multiplier"] - 1)
            else:
                bank_delta += bet["amount"]
        for uid, payout in payouts.items():
            legs[ledger.user_code(uid)] = payout
        legs[ledger.BANK] = bank_delta

        try:
            async with con.transaction():  # savepoint: fall back to refunds if the bank cannot pay
                await ledger.post(con, "roulette_spin", legs, meta={"chat_id": chat_id, "number": number, "color": color})
                refunded = False
        except ledger.InsufficientFunds:
            refund: dict[str, Decimal] = {ledger.ROULETTE_ESCROW: -stake_total}
            for bet in bets:
                key = ledger.user_code(bet["user_id"])
                refund[key] = refund.get(key, Decimal("0.00")) + bet["amount"]
            await ledger.post(con, "roulette_refund", refund, meta={"chat_id": chat_id})
            payouts = {}
            refunded = True
        await con.execute("DELETE FROM roulette_bets WHERE chat_id = $1", chat_id)
        return {"winners": list(payouts.items()), "refunded": refunded, "empty": False}
