"""Periodic background jobs."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

import asyncpg
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app import constants
from app.db import actions, borrow, ledger, stats
from app.utils.money import fmt_money

logger = logging.getLogger(__name__)


async def _loop(name: str, interval: float, job: Callable[[], Awaitable[None]], first_delay: float = 5.0) -> None:
    await asyncio.sleep(first_delay)
    while True:
        try:
            await job()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - a failed run must not kill the loop
            logger.exception("Background job %s failed", name)
        await asyncio.sleep(interval)


async def collect_loans(pool: asyncpg.Pool, bot: Bot) -> None:
    async with pool.acquire() as con:
        due = await borrow.due_loans(con)
    for row in due:
        async with pool.acquire() as con:
            loan = await borrow.settle(con, row["id"])
        if not loan:
            continue
        logger.info("Loan %s settled: %s", loan["id"], loan["amount_due"])
        text_lender = f"💰 Займ #{loan['id']} возвращён: вы получили {fmt_money(loan['amount_due'])}."
        text_borrower = f"💸 Срок займа #{loan['id']} истёк: с вас списано {fmt_money(loan['amount_due'])}."
        for uid, text in ((loan["lender_id"], text_lender), (loan["borrower_id"], text_borrower)):
            try:
                await bot.send_message(uid, text)
            except TelegramAPIError as exc:
                logger.info("Could not notify %s about loan %s: %s", uid, loan["id"], exc)


async def housekeeping(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as con:
        removed = await actions.purge(con)
        if removed:
            logger.debug("Purged %d expired actions", removed)


async def take_snapshot(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as con:
        await stats.snapshot(con)


async def grow_number_pot(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as con, con.transaction():
        pot = await ledger.balance(con, ledger.NUMBER_POT)
        if pot >= constants.NUMBER_POT_MAX:
            return
        amount = min(constants.NUMBER_POT_GROWTH, constants.NUMBER_POT_MAX - pot)
        try:
            await ledger.post(
                con, "number_pot_growth", {ledger.BANK: -amount, ledger.NUMBER_POT: amount}
            )
        except ledger.InsufficientFunds:
            logger.warning("Bank cannot fund the number pot")


def start_background(pool: asyncpg.Pool, bot: Bot) -> list[asyncio.Task]:
    jobs = [
        ("loans", 30, lambda: collect_loans(pool, bot)),
        ("housekeeping", 600, lambda: housekeeping(pool)),
        ("snapshot", 3600, lambda: take_snapshot(pool)),
        ("number_pot", 3600, lambda: grow_number_pot(pool)),
    ]
    tasks = [asyncio.create_task(_loop(n, i, j), name=f"bg-{n}") for n, i, j in jobs]
    logger.info("Started %d background jobs", len(tasks))
    return tasks
