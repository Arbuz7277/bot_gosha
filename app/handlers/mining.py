"""Proof-of-work mining mini game."""
from __future__ import annotations

import json
import logging
import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app import constants
from app.db import mining
from app.middlewares import RequireUser
from app.utils.filters import IsOwner
from app.utils.text import args_of, esc

logger = logging.getLogger(__name__)

router = Router(name="mining")
registered = Router(name="mining-registered")
registered.message.middleware(RequireUser())
router.include_router(registered)

NONCE_RE = re.compile(r"\d{1,40}")


@registered.message(Command("mine", "miner"))
async def cmd_mine(message: Message, pool, user) -> None:
    tokens = args_of(message)
    async with pool.acquire() as con:
        state = await mining.get_state(con)
    seed, target = state["seed"], int(state["target_hex"], 16)
    difficulty = round(constants.MINE_MAX_TARGET / target)
    if len(tokens) != 1:
        await message.reply(
            "🪙 <b>Майнинг</b>\n\n🎯 <b>Цель</b>\nНайти число nonce, при котором "
            "<code>int(sha256(seed + str(nonce)), 16) &lt; target</code>\nSHA-256 считается от UTF-8 строки.\n\n"
            f"📋 <b>Информация</b>\n• Seed: <code>{seed}</code>\n• Target: <code>{target:064x}</code> (Difficulty {difficulty})\n"
            f"• Reward: {constants.MINE_REWARD} coins\n\n📝 Используйте <code>/miner nonce</code> для получения награды."
        )
        return
    if not NONCE_RE.fullmatch(tokens[0]):
        await message.reply("Nonce должен быть неотрицательным целым числом (до 40 цифр).")
        return
    async with pool.acquire() as con:
        block = await mining.submit(con, user["id"], str(int(tokens[0])))
    if block is None:
        await message.reply("Nonce неверный!")
        return
    await message.reply(
        f"Поздравляю! Вы получили <code>{constants.MINE_REWARD}</code> коинов!\n\n"
        "--- Текущий блок ---\n"
        f"- Хеш: <code>{block['hash']}</code>\n- Seed: <code>{block['seed']}</code>\n"
        f"- Target: <code>{block['target']:064x}</code>\n- Nonce: <code>{block['nonce']}</code>\n\n"
        "--- Новые данные ---\n"
        f"- Seed: <code>{block['new_seed']}</code>\n- Target: <code>{block['new_target']:064x}</code>"
    )


@router.message(Command("miner_info"))
async def cmd_miner_info(message: Message, pool) -> None:
    async with pool.acquire() as con:
        total = await mining.block_count(con)
    await message.reply(f"All blocks: {total}\n\nWrite /miner")


@router.message(Command("mine_history"), IsOwner())
async def cmd_mine_history(message: Message, pool) -> None:
    limit = 10
    async with pool.acquire() as con:
        blocks = await mining.last_blocks(con, limit)
    data = [
        {"id": b["id"], "seed": b["seed"], "hash": b["hash"], "nonce": b["nonce"], "target": b["target_hex"],
         "difficulty": b["difficulty"], "user_id": b["user_id"], "found_at": b["found_at"].isoformat()}
        for b in blocks
    ]
    await message.reply(f"Последние {limit} блоков\n\n<pre>{esc(json.dumps(data, indent=2))}</pre>"[:4000])
