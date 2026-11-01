"""Referral codes."""
from __future__ import annotations

import logging
import secrets

from app import constants
from app.db import ledger

logger = logging.getLogger(__name__)


async def get_or_create_code(con, user_id: int) -> int:
    async with con.transaction():
        code = await con.fetchval("SELECT code FROM referral_codes WHERE user_id = $1", user_id)
        if code:
            return code
        for _ in range(50):
            candidate = 100_000 + secrets.randbelow(900_000)
            inserted = await con.fetchval(
                "INSERT INTO referral_codes (user_id, code) VALUES ($1, $2) "
                "ON CONFLICT DO NOTHING RETURNING code",
                user_id, candidate,
            )
            if inserted:
                return inserted
            existing = await con.fetchval("SELECT code FROM referral_codes WHERE user_id = $1", user_id)
            if existing:
                return existing
        raise RuntimeError("could not allocate a referral code")


async def uses_count(con, user_id: int) -> int:
    return await con.fetchval("SELECT count(*) FROM referral_uses WHERE inviter_id = $1", user_id)


async def activate(con, invitee_id: int, code_text: str) -> tuple[str, int | None]:
    """Activate a code. Returns (status, inviter_id).

    status: ok | bad_code | own_code | already_used | circular
    """
    if not code_text.isdigit() or len(code_text) > 9:
        return "bad_code", None
    async with con.transaction():
        inviter_id = await con.fetchval("SELECT user_id FROM referral_codes WHERE code = $1", int(code_text))
        if inviter_id is None:
            return "bad_code", None
        if inviter_id == invitee_id:
            return "own_code", None
        if await con.fetchval("SELECT 1 FROM referral_uses WHERE invitee_id = $1", invitee_id):
            return "already_used", inviter_id
        if await con.fetchval(
            "SELECT 1 FROM referral_uses WHERE invitee_id = $1 AND inviter_id = $2", inviter_id, invitee_id
        ):
            return "circular", inviter_id
        bonus = constants.REFERRAL_BONUS
        tx_id = await ledger.post(
            con,
            "referral",
            {
                ledger.EMISSION: -2 * bonus,
                ledger.user_code(inviter_id): bonus,
                ledger.user_code(invitee_id): bonus,
            },
            initiator_id=invitee_id,
            meta={"inviter": inviter_id, "invitee": invitee_id},
        )
        await con.execute(
            "INSERT INTO referral_uses (invitee_id, inviter_id, tx_id) VALUES ($1, $2, $3)",
            invitee_id, inviter_id, tx_id,
        )
    logger.info("Referral code activated: invitee=%s inviter=%s", invitee_id, inviter_id)
    return "ok", inviter_id
