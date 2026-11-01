"""Quotes: /q, /sq, /mq and the voting buttons."""
from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import constants
from app.callbacks import QuoteCb, QuotePageCb
from app.db import quotes, users
from app.middlewares import RequireUser
from app.utils.telegram import safe_edit
from app.utils.text import args_of, esc
from app.utils.timeutils import fmt_datetime

logger = logging.getLogger(__name__)

router = Router(name="quotes")
registered = Router(name="quotes-registered")
registered.message.middleware(RequireUser())
registered.callback_query.middleware(RequireUser())
router.include_router(registered)

QUOTE_HELP = (
    "❌ <b>Вы ввели пустую цитату или не перевели строку после команды.</b>\n\n"
    "💡 <b>Пример</b>\n<blockquote>/q\nПишите свою цитату здесь.\nВ цитатах можно переводить строки.</blockquote>"
)


def _quote_kb(quote) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{quote['likes']} 👍", callback_data=QuoteCb(qid=quote["id"], act="like"))
    kb.button(text=f"{quote['dislikes']} 👎", callback_data=QuoteCb(qid=quote["id"], act="dislike"))
    kb.button(text="⚠ Report", callback_data=QuoteCb(qid=quote["id"], act="report"))
    kb.adjust(2, 1)
    return kb.as_markup()


def _quote_text(quote) -> str:
    author = quote["current_name"] or quote["author_name"]
    return (
        f"💬 Цитата №{quote['id']}\n<blockquote>{esc(quote['text'])}</blockquote>\n\n"
        f"👤 <b>Автор:</b> {esc(author)}\n⏰ <b>Дата:</b> {fmt_datetime(quote['created_at'])} МСК"
    )


@registered.message(Command("q"))
async def cmd_quote(message: Message, pool, user) -> None:
    body = (message.text or "").split("\n", 1)[1].strip() if "\n" in (message.text or "") else ""
    if not body:
        await message.reply(QUOTE_HELP)
        return
    if len(body) > constants.QUOTE_MAX_LEN:
        await message.reply(f"❌ Цитата слишком длинная (максимум {constants.QUOTE_MAX_LEN} символов).")
        return
    async with pool.acquire() as con:
        quote_id = await quotes.add(con, user["id"], user["name"], body)
    await message.reply(
        f"✅ <b>Вы добавили цитату №{quote_id}</b>\n\n📝 Все свои цитаты: /my_quotes"
    )


@router.message(Command("sq", "search_quote"))
async def cmd_search_quote(message: Message, pool, user=None, settings=None) -> None:
    tokens = args_of(message)
    async with pool.acquire() as con:
        if tokens and tokens[0].lower() == "m":
            is_staff = user is not None and (user["is_admin"] or user["id"] in settings.owner_ids)
            if not is_staff:
                return
            ids = await quotes.reported_ids(con)
            await message.reply("ID of reported quotes\n\n" + (", ".join(map(str, ids)) or "—"))
            return
        if tokens and tokens[0].isdigit():
            quote_id = int(tokens[0])
        else:
            quote_id = await quotes.random_id(con)
        quote = await quotes.get(con, quote_id) if quote_id else None
    if quote is None or quote["verified"] is False:
        await message.reply("❌ <b>Цитата не найдена.</b> Создайте свою с помощью /q")
        return
    await message.reply(_quote_text(quote), reply_markup=_quote_kb(quote))


async def _page_view(pool, user_id: int, page: int) -> tuple[str, InlineKeyboardMarkup] | None:
    async with pool.acquire() as con:
        rows, total = await quotes.user_quotes(con, user_id, page, constants.QUOTES_PER_PAGE)
    if total == 0:
        return None
    pages = (total + constants.QUOTES_PER_PAGE - 1) // constants.QUOTES_PER_PAGE
    text = f"💬 <b>Ваши цитаты</b>\nСтраница: {page}/{pages}"
    for row in rows:
        text += f"\n\n№{row['id']} ¦ {esc(row['text'][:20])}...\nДата: {fmt_datetime(row['created_at'])}"
    kb = InlineKeyboardBuilder()
    kb.button(text="<", callback_data=QuotePageCb(owner=user_id, page=max(1, page - 1)))
    kb.button(text=">", callback_data=QuotePageCb(owner=user_id, page=min(pages, page + 1)))
    return text, kb.as_markup()


@registered.message(Command("mq", "my_quotes"))
async def cmd_my_quotes(message: Message, pool, user) -> None:
    view = await _page_view(pool, user["id"], 1)
    if view is None:
        await message.reply("❌ <b>Вы ещё не создали ни одной цитаты :(</b>\nСоздайте первую с помощью /q")
        return
    await message.reply(view[0], reply_markup=view[1])


@registered.callback_query(QuotePageCb.filter())
async def on_quote_page(call: CallbackQuery, callback_data: QuotePageCb, pool) -> None:
    if call.from_user.id != callback_data.owner:
        await call.answer("❌ Это не ваши цитаты!", show_alert=True)
        return
    view = await _page_view(pool, callback_data.owner, max(1, callback_data.page))
    if view:
        await safe_edit(call, view[0], view[1])
    await call.answer()


@registered.callback_query(QuoteCb.filter())
async def on_quote_action(call: CallbackQuery, callback_data: QuoteCb, bot: Bot, pool, settings) -> None:
    async with pool.acquire() as con:
        quote = await quotes.get(con, callback_data.qid)
        if quote is None:
            await call.answer("Цитата не найдена.", show_alert=True)
            return
        if callback_data.act in ("like", "dislike"):
            await quotes.vote(con, quote["id"], call.from_user.id, 1 if callback_data.act == "like" else -1)
            quote = await quotes.get(con, quote["id"])
            await safe_edit(call, _quote_text(quote), _quote_kb(quote))
            await call.answer()
            return
        # report
        if quote["verified"]:
            await call.answer("Эта цитата уже проверена администрацией.", show_alert=True)
            return
        await quotes.set_verified(con, quote["id"], False)
        staff = set(settings.owner_ids) | set(await users.admin_ids(con))
    logger.info("Quote %s reported by %s", quote["id"], call.from_user.id)
    for uid in staff:
        try:
            await bot.send_message(uid, f"⚠ Жалоба на цитату №{quote['id']}\n<blockquote>{esc(quote['text'])}</blockquote>\n"
                                        f"Одобрить: /qverify {quote['id']}  Удалить: /qdel {quote['id']}")
        except TelegramAPIError:
            continue
    await safe_edit(call, "⚠ Цитата скрыта до проверки модератором.")
    await call.answer("Жалоба отправлена")
