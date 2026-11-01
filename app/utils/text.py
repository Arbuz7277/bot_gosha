"""Small text helpers shared by handlers."""
from __future__ import annotations

import html

from aiogram.types import Message


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{esc(name)}</a>'


def args_of(message: Message) -> list[str]:
    """Tokens after the first word (works for '/cmd a b' and for text triggers)."""
    return (message.text or "").split()[1:]


def raw_args(message: Message) -> str:
    """Everything after the first word, keeping line breaks."""
    parts = (message.text or "").split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def user_link(user_id: int, name: str, username: str | None, *, show_username: bool = True) -> str:
    if username and show_username:
        return f'<a href="https://t.me/{esc(username)}">{esc(name)}</a>'
    return mention(user_id, name)
