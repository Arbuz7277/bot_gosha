"""Settings menu, nickname and account deletion."""
from __future__ import annotations

import logging

import emoji
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import MenuCb, SettingCb
from app.db import actions, users
from app.middlewares import RequireUser
from app.services import keyboards
from app.services.action_registry import action_handler
from app.utils.filters import Trigger
from app.utils.telegram import safe_edit
from app.utils.text import esc, raw_args

logger = logging.getLogger(__name__)

router = Router(name="settings")
router.message.middleware(RequireUser())
router.callback_query.middleware(RequireUser())

CONFID = {
    "transfer_check": "Чеки о переводах",
    "hide_username": "Скрывать юзернейм",
    "hide_balance": "Скрывать баланс",
    "hide_top": "Скрывать из топа",
}
NOTIFICATIONS = {"casino_warning": "Предупреждение казино"}


def _menu_kb(owner: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔒 Конфиденциальность", callback_data=MenuCb(action="confid", owner=owner))
    kb.button(text="🔔 Уведомления", callback_data=MenuCb(action="notifications", owner=owner))
    kb.button(text="⬅️ Меню", callback_data=MenuCb(action="menu", owner=owner))
    kb.adjust(1)
    return kb.as_markup()


def _toggle_kb(user, owner: int, items: dict[str, str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, label in items.items():
        current = bool(user[key])
        kb.button(
            text=f"{'✅' if current else '❌'} {label}",
            callback_data=SettingCb(owner=owner, key=key, value=0 if current else 1),
        )
    kb.button(text="⬅️ Назад", callback_data=MenuCb(action="settings", owner=owner))
    kb.adjust(1)
    return kb.as_markup()


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    await message.reply("⚙️ Настройки\n\nВыберите раздел снизу", reply_markup=_menu_kb(message.from_user.id))


@router.callback_query(MenuCb.filter(F.action.in_({"settings", "confid", "notifications"})))
async def on_settings_menu(call: CallbackQuery, callback_data: MenuCb, user) -> None:
    if call.from_user.id != callback_data.owner:
        await call.answer("❌ Это не ваши настройки!", show_alert=True)
        return
    if callback_data.action == "settings":
        await safe_edit(call, "⚙️ Настройки\n\nВыберите раздел снизу", _menu_kb(callback_data.owner))
    elif callback_data.action == "confid":
        await safe_edit(call, "🔒 <b>Конфиденциальность</b>", _toggle_kb(user, callback_data.owner, CONFID))
    else:
        await safe_edit(call, "🔔 <b>Уведомления</b>", _toggle_kb(user, callback_data.owner, NOTIFICATIONS))
    await call.answer()


@router.callback_query(SettingCb.filter())
async def on_setting_toggle(call: CallbackQuery, callback_data: SettingCb, pool) -> None:
    if call.from_user.id != callback_data.owner:
        await call.answer("❌ Это не ваши настройки!", show_alert=True)
        return
    if callback_data.key not in users.SETTING_COLUMNS:
        await call.answer("Неизвестная настройка.", show_alert=True)
        return
    async with pool.acquire() as con:
        await users.set_setting(con, callback_data.owner, callback_data.key, bool(callback_data.value))
        fresh = await users.get(con, callback_data.owner)
    items, title = (NOTIFICATIONS, "🔔 <b>Уведомления</b>") if callback_data.key in NOTIFICATIONS else (CONFID, "🔒 <b>Конфиденциальность</b>")
    await safe_edit(call, title, _toggle_kb(fresh, callback_data.owner, items))
    await call.answer("✅ Сохранено")


@router.message(Command("nick"))
async def cmd_nick(message: Message, pool, user) -> None:
    nick = emoji.replace_emoji(raw_args(message).split("\n")[0], replace="").strip()
    if not nick:
        await message.reply("❌ Ошибка!\n\nВведите ник после команды.\nИспользование:\n/nick nick123")
        return
    if not 3 <= len(nick) <= 32:
        await message.reply("❌ Ошибка!\n\nНик должен быть длиной от 3 до 32 символов.")
        return
    async with pool.acquire() as con:
        await users.set_name(con, user["id"], nick)
    logger.info("User %s changed nickname", user["id"])
    await message.reply(f"✅ Успешно!\n\nВы изменили свой ник на {esc(nick)}.")


@router.message(Trigger(".имя", "мое имя", "моё имя"))
async def cmd_my_name(message: Message, user) -> None:
    await message.reply(f"Твой ник: {esc(user['name'])}")


@router.message(Command("delete_account"))
@router.message(Trigger("удалить аккаунт", "удалить акк"))
async def cmd_delete_account(message: Message, pool, user) -> None:
    async with pool.acquire() as con:
        action_id = await actions.create(con, "delete_account", user["id"], {}, message.chat.id)
    await message.reply(
        "<b>Подтвердите удаление аккаунта.</b>\nОстаток коинов вернётся в банк, остальные данные будут удалены!",
        reply_markup=keyboards.confirm_kb(action_id, "УДАЛИТЬ", "ОТМЕНИТЬ"),
    )


@action_handler("delete_account")
async def confirm_delete_account(call: CallbackQuery, action, *, pool, **_) -> None:
    try:
        async with pool.acquire() as con:
            await users.delete_account(con, action["owner_id"])
    except ValueError:
        await safe_edit(call, "❌ Нельзя удалить аккаунт, пока есть активные займы.")
        await call.answer()
        return
    await safe_edit(call, "✅ Аккаунт удалён.")
    await call.answer()
