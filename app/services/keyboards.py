"""Reusable inline keyboards."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import ActionCb, MenuCb


def confirm_kb(action_id: str, yes: str = "ПОДТВЕРДИТЬ", no: str = "ОТМЕНА") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=yes, callback_data=ActionCb(id=action_id, choice="y"))
    kb.button(text=no, callback_data=ActionCb(id=action_id, choice="n"))
    kb.adjust(1)
    return kb.as_markup()


def choice_kb(action_id: str, options: list[tuple[str, str]], cancel: str = "ОТМЕНИТЬ") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for label, choice in options:
        kb.button(text=label, callback_data=ActionCb(id=action_id, choice=choice))
    kb.button(text=cancel, callback_data=ActionCb(id=action_id, choice="n"))
    kb.adjust(1)
    return kb.as_markup()


def main_menu_kb(owner: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Профиль", callback_data=MenuCb(action="profile", owner=owner))
    kb.button(text="🎁 Реферал", callback_data=MenuCb(action="referral", owner=owner))
    kb.button(text="⚙️ Настройки", callback_data=MenuCb(action="settings", owner=owner))
    kb.button(text="📖 Помощь", callback_data=MenuCb(action="help", owner=owner))
    kb.adjust(2)
    return kb.as_markup()


def register_kb(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Зарегистрироваться", url=f"https://t.me/{bot_username}?start=0")]]
    )
