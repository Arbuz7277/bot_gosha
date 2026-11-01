"""Proof-of-work mining mini game."""
from __future__ import annotations

import hashlib
import logging
import secrets
import statistics

import asyncpg

from app import constants
from app.db import ledger

logger = logging.getLogger(__name__)


def check_nonce(seed: str, nonce: str, target: int) -> tuple[bool, str]:
    digest = hashlib.sha256((seed + nonce).encode("utf-8")).hexdigest()
    return int(digest, 16) < target, digest


async def get_state(con) -> asyncpg.Record:
    return await con.fetchrow("SELECT seed, target_hex FROM mining_state WHERE id = 1")


async def block_count(con) -> int:
    return await con.fetchval("SELECT count(*) FROM mining_blocks")


async def last_blocks(con, limit: int = 10) -> list[asyncpg.Record]:
    rows = await con.fetch("SELECT * FROM mining_blocks ORDER BY id DESC LIMIT $1", limit)
    return list(reversed(rows))


def _retarget(target: int, times: list[float]) -> int:
    deltas = [max(b - a, 0.001) for a, b in zip(times, times[1:])]
    median = statistics.median(deltas)
    candidate = target / (constants.MINE_TARGET_TIME / median)
    candidate = min(constants.MINE_MAX_TARGET, min(target * 4, candidate))
    return int(max(target / 4, candidate))


async def submit(con, user_id: int, nonce: str) -> dict | None:
    """Try a nonce against the current block. Returns block info on success."""
    async with con.transaction():
        state = await con.fetchrow("SELECT seed, target_hex FROM mining_state WHERE id = 1 FOR UPDATE")
        seed, target = state["seed"], int(state["target_hex"], 16)
        ok, digest = check_nonce(seed, nonce, target)
        if not ok:
            return None

        difficulty = round(constants.MINE_MAX_TARGET / target)
        reward_tx = await ledger.post(
            con,
            "mining_reward",
            {ledger.EMISSION: -constants.MINE_REWARD, ledger.user_code(user_id): constants.MINE_REWARD},
            initiator_id=user_id,
            meta={"seed": seed, "nonce": nonce},
        )
        found_at = await con.fetchval(
            "INSERT INTO mining_blocks (seed, hash, nonce, target_hex, difficulty, user_id, reward_tx) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING found_at",
            seed, digest, nonce, state["target_hex"], difficulty, user_id, reward_tx,
        )
        new_target = target
        total = await con.fetchval("SELECT count(*) FROM mining_blocks")
        window = constants.MINE_MEDIAN_WINDOW
        if total > window and total % window == 0:
            rows = await con.fetch(
                "SELECT EXTRACT(EPOCH FROM found_at)::float AS t FROM mining_blocks "
                "ORDER BY found_at DESC, id DESC LIMIT $1",
                window + 1,
            )
            new_target = _retarget(target, [r["t"] for r in reversed(rows)])
        await con.execute(
            "UPDATE mining_state SET seed = $1, target_hex = $2 WHERE id = 1",
            digest, f"{new_target:064x}",
        )
        logger.info("Block found by user %s (difficulty %s)", user_id, difficulty)
        return {
            "hash": digest,
            "seed": seed,
            "nonce": nonce,
            "target": target,
            "new_seed": digest,
            "new_target": new_target,
            "found_at": found_at,
        }
