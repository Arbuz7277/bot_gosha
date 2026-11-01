"""Peer-to-peer loans."""
from __future__ import annotations

import logging
from decimal import Decimal

import asyncpg

from app import constants
from app.db import ledger

logger = logging.getLogger(__name__)


def amount_due(amount: Decimal, percent: int) -> Decimal:
    return ledger.q(amount + amount * percent / 100)


async def create_request(
    con, borrower_id: int, lender_id: int, amount: Decimal, percent: int, term_hours: int
) -> int | None:
    """Create a pending request. Returns its id or None if one is already pending."""
    async with con.transaction():
        await con.execute(
            "UPDATE borrow_requests SET status = 'expired', settled_at = now() "
            "WHERE status = 'pending' AND created_at < now() - make_interval(hours => $1)",
            constants.BORROW_REQUEST_TTL_HOURS,
        )
        dup = await con.fetchval(
            "SELECT 1 FROM borrow_requests WHERE status = 'pending' AND borrower_id = $1 AND lender_id = $2",
            borrower_id, lender_id,
        )
        if dup:
            return None
        return await con.fetchval(
            "INSERT INTO borrow_requests (borrower_id, lender_id, amount, percent, term_hours, amount_due) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            borrower_id, lender_id, amount, percent, term_hours, amount_due(amount, percent),
        )


async def accept(con, borrower_id: int, lender_id: int) -> asyncpg.Record | None:
    """Lender accepts the pending request: the principal moves lender -> borrower."""
    async with con.transaction():
        request = await con.fetchrow(
            "SELECT * FROM borrow_requests WHERE status = 'pending' AND borrower_id = $1 AND lender_id = $2 "
            "AND created_at > now() - make_interval(hours => $3) ORDER BY id LIMIT 1 FOR UPDATE",
            borrower_id, lender_id, constants.BORROW_REQUEST_TTL_HOURS,
        )
        if not request:
            return None
        tx_id = await ledger.post(
            con,
            "borrow_issue",
            {ledger.user_code(lender_id): -request["amount"], ledger.user_code(borrower_id): request["amount"]},
            initiator_id=lender_id,
            meta={"request_id": request["id"], "percent": request["percent"]},
        )
        return await con.fetchrow(
            "UPDATE borrow_requests SET status = 'active', activated_at = now(), "
            "due_at = now() + make_interval(hours => term_hours), issue_tx = $2 WHERE id = $1 RETURNING *",
            request["id"], tx_id,
        )


async def due_loans(con, limit: int = 50) -> list[asyncpg.Record]:
    return await con.fetch(
        "SELECT id FROM borrow_requests WHERE status = 'active' AND due_at <= now() ORDER BY due_at LIMIT $1",
        limit,
    )


async def settle(con, loan_id: int) -> asyncpg.Record | None:
    """Collect a due loan (the borrower may go negative: it is a debt collection)."""
    async with con.transaction():
        loan = await con.fetchrow(
            "SELECT * FROM borrow_requests WHERE id = $1 AND status = 'active' AND due_at <= now() "
            "FOR UPDATE SKIP LOCKED",
            loan_id,
        )
        if not loan:
            return None
        borrower = ledger.user_code(loan["borrower_id"])
        tx_id = await ledger.post(
            con,
            "borrow_repay",
            {borrower: -loan["amount_due"], ledger.user_code(loan["lender_id"]): loan["amount_due"]},
            meta={"request_id": loan["id"]},
            overdraft=(borrower,),
        )
        return await con.fetchrow(
            "UPDATE borrow_requests SET status = 'repaid', settled_at = now(), repay_tx = $2 "
            "WHERE id = $1 RETURNING *",
            loan_id, tx_id,
        )


async def has_active_loans(con, user_id: int) -> bool:
    return bool(
        await con.fetchval(
            "SELECT 1 FROM borrow_requests WHERE status = 'active' AND (borrower_id = $1 OR lender_id = $1) LIMIT 1",
            user_id,
        )
    )
