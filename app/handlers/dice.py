"""Duel with Telegram dice."""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import constants
from app.db import actions, ledger, users
from app.middlewares import RequireUser
from app.services import keyboards
from app.services.action_registry import action_handler
from app.utils.filters import Trigger
from app.utils.money import fmt, fmt_money, parse_amount, quantize
from app.utils.telegram import safe_edit
from app.utils.text import args_of, mention

logger = logging.getLogger(__name__)

router = Router(name="dice")
router.message.middleware(RequireUser())

USAGE = ("❌ Неверные аргументы!\n\nИспользование:\n<code>/dice &lt;ставка&gt;</code> (ответом на сообщение)\n"
         "или <code>/dice &lt;@username|id&gt; &lt;ставка&gt;</code>")


@router.message(Command("dice"))
@router.message(Trigger(".кости", "дайс", with_args=True))
async def cmd_dice(message: Message, pool, user) -> None:
    tokens = args_of(message)
    reply = message.reply_to_message
    async with pool.acquire() as con:
        if len(tokens) == 1 and reply and reply.from_user:
            opponent = await users.get(con, reply.from_user.id)
            bid_token = tokens[0]
        elif len(tokens) == 2:
            opponent = await users.find(con, tokens[0])
            bid_token = tokens[1]
        else:
            await message.reply(USAGE)
            return
        bid = parse_amount(bid_token, all_value=user["balance"])
        if bid is None or bid <= 0:
            await message.reply("❌ Введите положительную ставку!")
            return
        if opponent is None:
            await message.reply("❌ Игрок не зарегистрирован!")
            return
        if opponent["id"] == user["id"]:
            await message.reply("❌ Нельзя играть с самим собой!")
            return
        if bid > quantize(user["balance"]):
            await message.reply("❌ У вас недостаточно средств!")
            return
        if bid > quantize(opponent["balance"]):
            await message.reply("❌ У игрока недостаточно средств")
            return
        action_id = await actions.create(
            con, "dice", opponent["id"],
            {"challenger": user["id"], "bid": str(bid), "chat_id": message.chat.id,
             "participants": [user["id"], opponent["id"]]},
            message.chat.id,
        )
    await message.answer(
        f"{mention(opponent['id'], opponent['name'])}, {mention(user['id'], user['name'])} "
        f"хочет сыграть с вами в кости на {fmt_money(bid)}.",
        reply_markup=keyboards.confirm_kb(action_id, "ПРИНЯТЬ", "ОТКЛОНИТЬ"),
    )


@action_handler("dice")
async def accept_dice(call: CallbackQuery, action, *, pool, bot: Bot, runtime, **_) -> None:
    payload = action["payload"]
    challenger, opponent = payload["challenger"], action["owner_id"]
    bid = Decimal(payload["bid"])
    chat_id = payload["chat_id"]
    if challenger in runtime.busy_dice or opponent in runtime.busy_dice:
        await safe_edit(call, "❌ Один из игроков уже участвует в другой игре.")
        await call.answer()
        return
    runtime.busy_dice.update((challenger, opponent))
    await safe_edit(call, "🎲 Игра началась!")
    await call.answer()
    asyncio.create_task(_play(pool, bot, runtime, chat_id, challenger, opponent, bid))


async def _play(pool, bot: Bot, runtime, chat_id: int, challenger: int, opponent: int, bid: Decimal) -> None:
    try:
        async with pool.acquire() as con:
            first = await users.get(con, challenger)
            second = await users.get(con, opponent)
        if not first or not second:
            await bot.send_message(chat_id, "❌ Игра отменена: игрок не найден.")
            return
        await bot.send_message(chat_id, f"{mention(challenger, first['name'])} бросает кубик...")
        d1 = (await bot.send_dice(chat_id, emoji="🎲")).dice.value
        await asyncio.sleep(4)
        await bot.send_message(chat_id, f"{mention(opponent, second['name'])} бросает кубик...")
        d2 = (await bot.send_dice(chat_id, emoji="🎲")).dice.value
        await asyncio.sleep(4)

        if d1 == d2:
            await bot.send_message(chat_id, f"🤝 Ничья ({d1}:{d2})! Ставки не списаны.")
            return
        winner, loser = (challenger, opponent) if d1 > d2 else (opponent, challenger)
        names = {challenger: first["name"], opponent: second["name"]}
        commission = quantize(bid * constants.COMMISSION_DICE / 100)
        try:
            async with pool.acquire() as con:
                await ledger.post(
                    con, "dice",
                    {ledger.user_code(loser): -bid, ledger.user_code(winner): bid - commission, ledger.BANK: commission},
                    initiator_id=winner, meta={"d1": d1, "d2": d2, "chat_id": chat_id},
                )
        except ledger.InsufficientFunds:
            await bot.send_message(chat_id, "❌ Игра отменена: у проигравшего не хватает коинов.")
            return
        logger.info("Dice: winner=%s loser=%s bid=%s", winner, loser, bid)
        await bot.send_message(
            chat_id,
            f"🎲 {d1}:{d2}\n🏆 {mention(winner, names[winner])} выиграл {fmt_money(bid - commission)} "
            f"(комиссия {fmt(commission)}).",
        )
    except TelegramAPIError as exc:
        logger.warning("Dice game aborted: %s", exc)
    except Exception:  # noqa: BLE001
        logger.exception("Dice game crashed")
    finally:
        runtime.busy_dice.discard(challenger)
        runtime.busy_dice.discard(opponent)
