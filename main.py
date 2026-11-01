"""Entry point: connects the database, builds the bot and starts polling."""
from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import ConfigError, load_settings
from app.db import create_pool, ledger, run_migrations
from app.handlers import setup_routers
from app.logging_setup import setup_logging
from app.middlewares import setup_middlewares
from app.services.background import start_background
from app.services.runtime import Runtime

logger = logging.getLogger("gosha")


async def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc
    setup_logging(settings.log_level, settings.log_dir)
    logger.info("Starting Gosha bot")

    pool = await create_pool(settings.dsn)
    tasks: list[asyncio.Task] = []
    bot: Bot | None = None
    try:
        await run_migrations(pool)
        async with pool.acquire() as con:
            report = await ledger.reconcile(con)
        if report["mismatches"] or report["unbalanced"] or report["ledger_sum"] != 0:
            logger.error("Ledger inconsistency detected: %s (run /audit repair)", report)
        else:
            logger.info("Ledger audit passed (global sum = 0)")

        bot = Bot(
            token=settings.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
        )
        me = await bot.me()
        if not settings.bot_username:
            object.__setattr__(settings, "bot_username", me.username or "")
        logger.info("Authorized as @%s (id=%s)", me.username, me.id)

        runtime = Runtime()
        dp = Dispatcher(pool=pool, settings=settings, runtime=runtime)
        setup_middlewares(dp, pool, settings, runtime)
        setup_routers(dp)

        tasks = start_background(pool, bot)
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("Polling started")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down")
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if bot is not None:
            await bot.session.close()
        await pool.close()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
