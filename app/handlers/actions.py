"""Dispatcher for single-use confirmation buttons (see services.action_registry)."""
from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from app.callbacks import ActionCb
from app.db import actions
from app.services.action_registry import HANDLERS
from app.utils.telegram import safe_edit

logger = logging.getLogger(__name__)
router = Router(name="actions")


@router.callback_query(ActionCb.filter())
async def on_action(call: CallbackQuery, callback_data: ActionCb, pool, bot: Bot, settings, runtime, user=None) -> None:
    uid = call.from_user.id
    cancel = callback_data.choice == "n"

    async with pool.acquire() as con:
        row = await actions.peek(con, callback_data.id)
    if row is None:
        await call.answer("⌛ Кнопка устарела или уже использована.", show_alert=True)
        return

    participants = set(row["payload"].get("participants", []))
    allowed = {row["owner_id"]} | participants
    if (cancel and uid not in allowed) or (not cancel and uid != row["owner_id"]):
        await call.answer("❌ Это действие не для вас!", show_alert=True)
        return

    async with pool.acquire() as con:
        taken = await actions.take(con, callback_data.id)
    if taken is None:
        await call.answer("⌛ Кнопка уже использована.", show_alert=True)
        return

    if cancel:
        await safe_edit(call, "❌ Отменено.")
        await call.answer()
        return

    handler = HANDLERS.get(taken["kind"])
    if handler is None:
        logger.error("No handler for action kind %r", taken["kind"])
        await call.answer("Ошибка: неизвестное действие.", show_alert=True)
        return

    logger.info("Action %s confirmed by user=%s choice=%s", taken["kind"], uid, callback_data.choice)
    await handler(
        call, taken, choice=callback_data.choice, pool=pool, bot=bot,
        settings=settings, runtime=runtime, user=user,
    )
