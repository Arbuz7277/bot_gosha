"""Custom aiogram filters."""
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.config import Settings


class Trigger(BaseFilter):
    """Match plain-text aliases ("farm", "топ чата", "pay 5 @user").

    With ``with_args=True`` the alias may be followed by arguments.
    """

    def __init__(self, *phrases: str, with_args: bool = False) -> None:
        self.phrases = tuple(p.lower() for p in phrases)
        self.with_args = with_args

    async def __call__(self, message: Message) -> bool:
        text = (message.text or "").strip().lower()
        if not text or text.startswith("/"):
            return False
        for phrase in self.phrases:
            if text == phrase or (self.with_args and text.startswith(phrase + " ")):
                return True
        return False


class IsOwner(BaseFilter):
    async def __call__(self, message: Message, settings: Settings) -> bool:
        return message.from_user is not None and message.from_user.id in settings.owner_ids


class IsAdmin(BaseFilter):
    """Bot admin (flag in the database) or owner."""

    async def __call__(self, message: Message, settings: Settings, user=None) -> bool:
        if message.from_user is None:
            return False
        if message.from_user.id in settings.owner_ids:
            return True
        return bool(user and user["is_admin"])


CASINO_WORDS = ("деп", "депнуть", "казик", ".казино")


def casino_trigger():
    """Matches 'casino ...', 'деп ...' and friends (first word, no slash)."""

    async def check(message: Message) -> bool:
        text = (message.text or "").strip().lower()
        if not text or text.startswith("/"):
            return False
        first = text.split()[0]
        return first == "casino" or first in CASINO_WORDS

    return check
