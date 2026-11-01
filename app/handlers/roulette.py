"""Roulette: bets are held in escrow until someone calls /spin."""
from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import constants
from app.callbacks import RouletteCb
from app.db import ledger, roulette, users
from app.middlewares import RequireUser
from app.utils.filters import Trigger
from app.utils.money import fmt, fmt_money, parse_amount, quantize
from app.utils.telegram import safe_edit
from app.utils.text import args_of, mention

logger = logging.getLogger(__name__)

router = Router(name="roulette")
router.message.middleware(RequireUser())
router.callback_query.middleware(RequireUser())

USAGE = "Играйте в рулетку! Аргументы:\n\n<code>/roulette &lt;black/red/green или число 0-36&gt; &lt;ставка&gt;</code>"
EMOJI = {"red": "🔴", "black": "⚫️", "green": "🟢"}


def _parse_bet_type(token: str) -> tuple[str, int] | None:
    token = token.lower()
    if token.isdigit():
        return (str(int(token)), 36) if int(token) <= 36 and len(token) <= 2 else None
    for color, aliases in constants.COLOR_ALIASES.items():
        if token in aliases:
            return color, (36 if color == "green" else 2)
    return None


def _cancel_kb(owner: int, chat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ ОТМЕНИТЬ СТАВКУ", callback_data=RouletteCb(owner=owner, chat=chat_id))
    return kb.as_markup()


@router.message(Command("roulette"))
@router.message(Trigger("рулетка", "крутить", with_args=True))
async def cmd_roulette(message: Message, pool, user) -> None:
    tokens = args_of(message)
    if len(tokens) != 2:
        await message.reply(USAGE)
        return
    parsed = _parse_bet_type(tokens[0])
    if parsed is None:
        await message.reply("❌ Пожалуйста, введите число от 0 до 36 или цвет!")
        return
    bet_type, multi = parsed
    bid = parse_amount(tokens[1], all_value=user["balance"])
    if bid is None:
        await message.reply(USAGE)
        return
    if bid < constants.MIN_BID:
        await message.reply(f"❌ Пожалуйста, введите ставку не меньше {fmt(constants.MIN_BID)} коина!")
        return
    try:
        async with pool.acquire() as con:
            placed = await roulette.place_bet(con, message.chat.id, user["id"], bid, bet_type, multi)
    except ledger.InsufficientFunds:
        await message.reply("❌ У вас недостаточно средств!")
        return
    if placed is None:
        await message.reply("❌ Банк не сможет выплатить выигрыш по такой ставке.")
        return
    logger.info("Roulette bet user=%s chat=%s %s on %s", user["id"], message.chat.id, bid, bet_type)
    await message.reply(
        f"🎯 Вы создали ставку {fmt_money(bid)} на {bet_type.upper()}\n\n🎰 Введите /spin чтобы покрутить рулетку.",
        reply_markup=_cancel_kb(user["id"], message.chat.id),
    )


@router.message(Command("spin"))
async def cmd_spin(message: Message, pool, user) -> None:
    chat_id = message.chat.id
    async with pool.acquire() as con:
        age = await roulette.first_bet_age(con, chat_id)
        if age is None:
            await message.reply("❌ На данный момент нет ни одной ставки в этом чате.")
            return
        if age < constants.KD_ROULETTE:
            await message.reply(f"⏳ Подождите ещё {int(constants.KD_ROULETTE - age) + 1} сек.")
            return
        number, color = secrets.choice(constants.ROULETTE_NUMBERS)
        result = await roulette.spin(con, chat_id, number, color)
        if result.get("empty"):
            await message.reply("❌ На данный момент нет ни одной ставки в этом чате.")
            return
        names = {}
        for uid, _ in result["winners"]:
            found = await users.get(con, uid)
            names[uid] = found["name"] if found else str(uid)

    text = f"Выпало {number}{EMOJI[color]}\n\n"
    if result["refunded"]:
        text += "Банк не смог выплатить все выигрыши — ставки возвращены."
    elif not result["winners"]:
        text += "Никто не выиграл..."
    else:
        text += "".join(f"{mention(uid, names[uid])} выиграл {fmt_money(payout)}\n" for uid, payout in result["winners"])
    logger.info("Roulette spin chat=%s number=%s winners=%d", chat_id, number, len(result["winners"]))
    await message.answer(text)


@router.message(Command("my_bid"))
async def cmd_my_bid(message: Message, pool, user) -> None:
    async with pool.acquire() as con:
        bets = await roulette.user_bets(con, message.chat.id, user["id"])
    if not bets:
        await message.reply("У вас нет ставок в данном чате...")
        return
    lines = "".join(f" - {fmt_money(b['amount'])} на {b['bet_type'].upper()}\n" for b in bets)
    await message.reply(f"💎 Ваши ставки:\n\n{lines}\n🎰 Введите /spin чтобы покрутить рулетку.",
                        reply_markup=_cancel_kb(user["id"], message.chat.id))


@router.callback_query(RouletteCb.filter())
async def on_cancel_bets(call: CallbackQuery, callback_data: RouletteCb, pool) -> None:
    if call.from_user.id != callback_data.owner:
        await call.answer("❌ Это не ваша ставка!", show_alert=True)
        return
    async with pool.acquire() as con:
        refunded = await roulette.cancel_user_bets(con, callback_data.chat, callback_data.owner)
    if refunded > 0:
        await safe_edit(call, f"✅ Ставки отменены, возвращено {fmt_money(refunded)}.")
    else:
        await safe_edit(call, "У вас нет активных ставок.")
    await call.answer()
