"""Inner middleware: the handler runs only for registered users."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.db import users
from app.services import keyboards, views

logger = logging.getLogger(__name__)


class RequireUser(BaseMiddleware):
    async def __call__(self, handler: Callable[[TelegramObject, dict], Awaitable[Any]], event: TelegramObject, data: dict) -> Any:
        if data.get("user") is not None:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer("Сначала зарегистрируйтесь: /start", show_alert=True)
            return None

        if isinstance(event, Message) and event.from_user:
            if event.chat.type == ChatType.PRIVATE:
                pool = data["pool"]
                async with pool.acquire() as con:
                    user, created = await users.register(
                        con, event.from_user.id, event.from_user.first_name or "Unknown", event.from_user.username
                    )
                data["user"] = user
                await event.reply(views.welcome_text(created))
                return await handler(event, data)
            settings: Settings = data["settings"]
            await event.reply(
                "Для этой команды нужна регистрация. Нажмите на кнопку ниже.",
                reply_markup=keyboards.register_kb(settings.bot_username),
            )
        return None
