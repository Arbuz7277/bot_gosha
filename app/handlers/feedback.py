"""Anonymous feedback: user -> owners, owners answer with /feedback answer."""
from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import constants
from app.callbacks import FeedbackCancelCb
from app.db import feedback
from app.middlewares import RequireUser
from app.utils.telegram import safe_edit
from app.utils.text import esc, raw_args
from app.utils.timeutils import fmt_datetime
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = Router(name="feedback")
registered = Router(name="feedback-registered")
registered.message.middleware(RequireUser())
router.include_router(registered)


class HasPendingFeedback(BaseFilter):
    async def __call__(self, message: Message, pool) -> bool:
        if message.chat.type != ChatType.PRIVATE or message.from_user is None:
            return False
        if message.text and message.text.startswith("/"):
            return False
        async with pool.acquire() as con:
            return await feedback.is_pending(con, message.from_user.id)


def _cancel_kb(owner: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ ОТМЕНИТЬ", callback_data=FeedbackCancelCb(owner=owner))
    return kb.as_markup()


@registered.message(Command("feedback", "fb"))
async def cmd_feedback(message: Message, bot: Bot, pool, user, settings) -> None:
    body = raw_args(message).strip()
    is_owner = user["id"] in settings.owner_ids
    if is_owner and body.lower().startswith("answer"):
        await _answer(message, bot, pool, body)
        return
    async with pool.acquire() as con:
        if not is_owner:
            left = await feedback.cooldown_left(con, user["id"])
            if left > 0:
                await message.reply(f"⏳ Подождите {int(left // 60)} мин {int(left % 60)} сек")
                return
        await feedback.start(con, user["id"])
    try:
        await bot.send_message(user["id"], "✉️ Отправьте анонимное сообщение разработчику.", reply_markup=_cancel_kb(user["id"]))
    except TelegramAPIError:
        await message.reply("❌ Не удалось написать вам в ЛС. Сначала напишите боту /start.")
        return
    if message.chat.type != ChatType.PRIVATE:
        await message.reply(f'Перейдите в <a href="https://t.me/{(await bot.me()).username}">ЛС</a>')


async def _answer(message: Message, bot: Bot, pool, body: str) -> None:
    parts = body.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.reply("Использование: <code>/feedback answer &lt;id&gt; &lt;текст&gt;</code>")
        return
    async with pool.acquire() as con:
        item = await feedback.get(con, int(parts[1]))
        if item is None or item["answered_at"] is not None:
            await message.reply("Айди не найден или на сообщение уже ответили!")
            return
        try:
            await bot.send_message(item["user_id"], f"✉️ Ответ от разработчика\n\n{esc(parts[2])}")
        except TelegramAPIError:
            await message.reply("❌ Сообщение не доставлено.")
            return
        await feedback.mark_answered(con, item["id"])
    await message.reply("✅ Сообщение отправлено!")


@router.callback_query(FeedbackCancelCb.filter())
async def on_cancel(call: CallbackQuery, callback_data: FeedbackCancelCb, pool) -> None:
    if call.from_user.id != callback_data.owner:
        await call.answer("❌ Это не ваша кнопка!", show_alert=True)
        return
    async with pool.acquire() as con:
        await feedback.cancel(con, callback_data.owner)
    await safe_edit(call, "❌ Отправка отменена.")
    await call.answer()


@router.message(HasPendingFeedback())
async def on_feedback_text(message: Message, bot: Bot, pool, settings) -> None:
    if not message.text:
        await message.reply("Отправьте, пожалуйста, текстовое сообщение.")
        return
    text = message.text[:3000]
    async with pool.acquire() as con:
        feedback_id = await feedback.submit(con, message.from_user.id, text)
    if feedback_id is None:
        return
    logger.info("Feedback #%s received", feedback_id)
    when = fmt_datetime(datetime.now(timezone.utc))
    delivered = False
    for owner in settings.owner_ids:
        try:
            await bot.send_message(
                owner,
                f"Пришло анонимное сообщение:\n\n<code>{esc(text)}</code>\n\nДата: <code>{when}</code>\n"
                f"Версия: <code>{constants.VERSION}</code>\nID: <code>{feedback_id}</code>",
            )
            delivered = True
        except TelegramAPIError as exc:
            logger.warning("Could not deliver feedback to owner %s: %s", owner, exc)
    await message.reply("✅ Сообщение отправлено!" if delivered else "❌ Произошла ошибка. Сообщение не доставлено.")
