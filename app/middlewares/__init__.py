"""Middlewares and their registration."""
from aiogram import Dispatcher

from app.middlewares.require_user import RequireUser
from app.middlewares.track import CallbackTrackMiddleware, MessageTrackMiddleware

__all__ = ["RequireUser", "setup_middlewares"]


def setup_middlewares(dp: Dispatcher, pool, settings, runtime) -> None:
    dp.message.outer_middleware(MessageTrackMiddleware(pool, settings, runtime))
    dp.callback_query.outer_middleware(CallbackTrackMiddleware(pool, settings, runtime))
