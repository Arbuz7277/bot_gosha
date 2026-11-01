"""Outer middlewares: load the user, track chats/activity, maintenance gate."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

import asyncpg
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.db import chats, users
from app.services.runtime import Runtime

logger = logging.getLogger(__name__)

CALLBACK_COOLDOWN = 1.0


class MessageTrackMiddleware(BaseMiddleware):
    def __init__(self, pool: asyncpg.Pool, settings: Settings, runtime: Runtime) -> None:
        self.pool = pool
        self.settings = settings
        self.runtime = runtime

    async def __call__(self, handler: Callable[[Message, dict], Awaitable[Any]], event: Message, data: dict) -> Any:
        tg_user = event.from_user
        if tg_user is None or tg_user.is_bot:
            return None

        async with self.pool.acquire() as con:
            user = await users.get(con, tg_user.id)
            await chats.track(con, event.chat, tg_user.id, registered=user is not None)
            if user is not None and user["username"] != tg_user.username:
                await users.sync_username(con, tg_user.id, tg_user.username)
                user = await users.get(con, tg_user.id)
        data["user"] = user

        text = event.text or ""
        if text.startswith("/"):
            logger.info("Command %s from user=%s chat=%s", text.split()[0], tg_user.id, event.chat.id)

        if self.runtime.maintenance and tg_user.id not in self.settings.owner_ids:
            if text.startswith("/"):
                await event.reply("🛠 Бот на техническом обслуживании. Попробуйте позже.")
            return None
        return await handler(event, data)


class CallbackTrackMiddleware(BaseMiddleware):
    def __init__(self, pool: asyncpg.Pool, settings: Settings, runtime: Runtime) -> None:
        self.pool = pool
        self.settings = settings
        self.runtime = runtime

    async def __call__(self, handler: Callable[[CallbackQuery, dict], Awaitable[Any]], event: CallbackQuery, data: dict) -> Any:
        tg_user = event.from_user
        if self.runtime.maintenance and tg_user.id not in self.settings.owner_ids:
            await event.answer("🛠 Технические работы", show_alert=True)
            return None
        if self.runtime.cooldowns.hit(("cb", tg_user.id), CALLBACK_COOLDOWN):
            await event.answer("⏳ Не так быстро!")
            return None
        async with self.pool.acquire() as con:
            data["user"] = await users.get(con, tg_user.id)
        logger.debug("Callback %s from user=%s", event.data, tg_user.id)
        return await handler(event, data)
