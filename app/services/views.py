"""Text builders shared between handlers."""
from __future__ import annotations

import asyncpg

from app.utils.money import coin_form, fmt, quantize
from app.utils.text import esc
from app.utils.timeutils import fmt_date

HELP_URL = "https://rentry.co/tg-gosha"


def profile_text(user: asyncpg.Record, *, is_admin: bool) -> str:
    balance_line = ""
    if not user["hide_balance"]:
        bal = quantize(user["balance"])
        balance_line = f"Баланс: <code>{fmt(bal)}</code> {coin_form(bal)}\n"
    username_line = ""
    if not user["hide_username"]:
        username = user["username"]
        username_line = f"Юзернейм: <code>{'@' + esc(username) if username else 'не указан'}</code>\n"
    return (
        f"📊 Профиль {esc(user['name'])}\n\n"
        f"Имя: <code>{esc(user['name'])}</code>\n"
        f"Дата регистрации(dd/mm/yy): <code>{fmt_date(user['registered_at'])}</code>\n"
        f"Ранг: {'Админ' if is_admin else 'Пользователь'}\n"
        f"Айди: <code>{user['gid']}</code>\n"
        f"{balance_line}{username_line}"
    )


def welcome_text(created: bool) -> str:
    if created:
        return (
            "✅ <b>Вы зарегистрированы!</b>\n\n"
            "Фармите коины командой /farm, а код друга активируйте через /code и получите бонус.\n"
            f'Список команд: <a href="{HELP_URL}">помощь</a>'
        )
    return "👋 С возвращением! Используйте /menu или /help."
