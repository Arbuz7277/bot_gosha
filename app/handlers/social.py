"""Rankings and referral commands."""
from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from app.db import chats, referral, stats
from app.handlers.start import apply_referral
from app.middlewares import RequireUser
from app.utils import charts
from app.utils.filters import Trigger
from app.utils.money import coin_form, fmt, quantize
from app.utils.text import args_of, esc, user_link

logger = logging.getLogger(__name__)

router = Router(name="social")
router.message.middleware(RequireUser())

MEDALS = ("🥇", "🥈", "🥉")


def _line(row, activity: dict[int, int] | None = None) -> str:
    pos = row["pos"]
    medal = MEDALS[pos - 1] if pos <= 3 else f"{pos}."
    link = user_link(row["id"], row["name"], row["username"])
    bal = quantize(row["bal"])
    line = f"{medal} {link} | {fmt(bal)} {coin_form(bal)}"
    if activity is not None:
        line += f" | {activity.get(row['id'], 0)} msg."
    return line


@router.message(Command("top"))
@router.message(Trigger("top", "топ чата", "топ чат"))
async def cmd_top(message: Message, pool, user, runtime) -> None:
    if message.chat.type == ChatType.PRIVATE:
        await message.reply("❌ Эта команда работает только в группах!")
        return
    if runtime.cooldowns.hit(("top", message.chat.id), 2):
        return
    async with pool.acquire() as con:
        rows = await stats.chat_top(con, message.chat.id)
        activity = await chats.activity_today(con, message.chat.id)
        by_day = await chats.activity_by_day(con, message.chat.id, 14)
    if not rows:
        await message.reply("💤 В чате пока нет пользователей с коинами.")
        return
    mine = next((r["pos"] for r in rows if r["id"] == user["id"]), None)
    text = "<b>ТОП ЧАТА</b>\n\n" + "\n".join(_line(r, activity) for r in rows[:15])
    text += f"\n\n📊 <b>Вы на</b> <code>{mine if mine else 'не в рейтинге'}</code> <b>месте.</b>"
    text += f"\n👥 <b>Всего в рейтинге:</b> <code>{len(rows)}</code>"
    text += f"\n💬 <b>Сообщений сегодня:</b> <code>{sum(activity.values())}</code>"
    await message.reply(text)
    try:
        png = await charts.bar_chart([d.strftime("%d.%m") for d, _ in by_day], [n for _, n in by_day],
                                     "Chat activity", "Days", "Messages")
        await message.answer_photo(BufferedInputFile(png, "activity.png"), caption="💬 Активность чата за 14 дней")
    except Exception:  # noqa: BLE001 - the text part is already delivered
        logger.exception("Could not render the activity chart")


@router.message(Command("global_top"))
@router.message(Trigger("global_top", "глобал топ", "глобальный топ"))
async def cmd_global_top(message: Message, pool, user) -> None:
    async with pool.acquire() as con:
        rows, total = await stats.global_top(con, 30)
        position = await stats.global_position(con, user["id"])
    body = "\n".join(
        f"{r['pos']}. {esc(r['name'])} | {fmt(r['bal'])} {coin_form(r['bal'])}" for r in rows
    )
    await message.reply(
        f"Глобальный топ\n\n<blockquote expandable>{body}</blockquote>\n\n"
        f"Вы на {position if position else 'не определено'} месте из {total}."
    )


@router.message(Command("referral"))
async def cmd_referral(message: Message, pool, user, settings) -> None:
    async with pool.acquire() as con:
        code = await referral.get_or_create_code(con, user["id"])
        used = await referral.uses_count(con, user["id"])
    await message.reply(
        f"Ваш реферальный код: <code>{code}</code>\nКод был активирован: <code>{used}</code> раз\n\n"
        f"https://t.me/{esc(settings.bot_username)}?start={code}\n"
        "Приглашайте людей по этой ссылке и получайте по 20 коинов за человека."
    )


@router.message(Command("code"))
async def cmd_code(message: Message, bot: Bot, pool, user) -> None:
    tokens = args_of(message)
    if len(tokens) != 1:
        await message.reply("❌ Ошибка!\n\nПример использования:\n/code 123456")
        return
    await apply_referral(message, bot, pool, user["id"], tokens[0])
