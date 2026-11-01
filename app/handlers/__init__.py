"""All routers are collected and connected here."""
from __future__ import annotations

import logging

from aiogram import Dispatcher, Router

from app.handlers import (
    actions,
    admin,
    borrow,
    chat_tools,
    dice,
    economy,
    feedback,
    games,
    mining,
    quotes,
    roulette,
    settings,
    shop,
    social,
    start,
    utility,
)

logger = logging.getLogger(__name__)

# Order matters: the first matching handler wins.
ROUTERS: tuple[Router, ...] = (
    actions.router,       # confirmation buttons
    start.router,
    start.registered,
    economy.router,
    games.router,
    roulette.router,
    dice.router,
    borrow.router,
    social.router,
    quotes.router,
    mining.router,
    shop.router,
    settings.router,
    admin.router,
    utility.router,
    feedback.router,      # catches the next private message of a user who started /feedback
    chat_tools.router,    # group tools and plain-text triggers go last
)


def setup_routers(dp: Dispatcher) -> None:
    for router in ROUTERS:
        dp.include_router(router)
    logger.info("Connected %d routers", len(ROUTERS))


__all__ = ["ROUTERS", "setup_routers"]
