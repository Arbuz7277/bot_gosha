"""/start, /help, /menu, /profile and the main menu callbacks."""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from app.callbacks import MenuCb
from app.db import referral, users
from app.middlewares import RequireUser
from app.services import keyboards, views
from app.utils.filters import Trigger
from app.utils.text import esc

logger = logging.getLogger(__name__)

router = Router(name="start")
registered = Router(name="start-registered")
registered.message.middleware(RequireUser())
registered.callback_query.middleware(RequireUser())

REFERRAL_ERRORS = {
    "bad_code": "❌ Реферальный код не существует.",
    "own_code": "❌ Это ваш собственный код!",
    "already_used": "❌ Вы уже активировали реферальный код.",
    "circular": "❌ Этот пользователь уже активировал ваш код.",
}


async def apply_referral(message: Message, bot: Bot, pool, invitee_id: int, code: str) -> None:
    async with pool.acquire() as con:
        status, inviter_id = await referral.activate(con, invitee_id, code)
    if status != "ok":
        await message.reply(REFERRAL_ERRORS.get(status, "❌ Не удалось активировать код."))
        return
    await message.reply("✅ Код активирован! Вам начислено 20 коинов.")
    try:
        await bot.send_message(inviter_id, "🎁 Пользователь активировал ваш код! Вам начислено 20 коинов.")
    except TelegramAPIError:
        logger.info("Could not notify inviter %s", inviter_id)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot, pool, user=None) -> None:
    tg = message.from_user
    created = False
    if user is None:
        async with pool.acquire() as con:
            user, created = await users.register(con, tg.id, tg.first_name or "Unknown", tg.username)
    code = (command.args or "").strip()
    await message.reply(views.welcome_text(created), reply_markup=keyboards.main_menu_kb(tg.id))
    if code and code != "0":
        await apply_referral(message, bot, pool, tg.id, code)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.reply(f'<a href="{views.HELP_URL}">Команды</a>')


@registered.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.reply("📋 <b>Меню</b>", reply_markup=keyboards.main_menu_kb(message.from_user.id))


@registered.message(Command("profile"))
@registered.message(Trigger("profile", "профиль", "проф", "акк", "аккаунт", ".инфа", "моя инфа", "мой профиль"))
async def cmd_profile(message: Message, pool, user, settings) -> None:
    target = user
    viewer_is_admin = user["is_admin"] or user["id"] in settings.owner_ids
    reply = message.reply_to_message
    if reply and reply.from_user and viewer_is_admin:
        async with pool.acquire() as con:
            found = await users.get(con, reply.from_user.id)
        if not found:
            await message.reply("❌ У пользователя нет аккаунта.")
            return
        target = found
    target_admin = target["is_admin"] or target["id"] in settings.owner_ids
    await message.reply(views.profile_text(target, is_admin=target_admin))


@registered.callback_query(MenuCb.filter(F.action.in_({"menu", "profile", "referral", "help"})))
async def on_menu(call: CallbackQuery, callback_data: MenuCb, pool, user, settings) -> None:
    if call.from_user.id != callback_data.owner:
        await call.answer("❌ Это не ваше меню!", show_alert=True)
        return
    action = callback_data.action
    markup = keyboards.main_menu_kb(callback_data.owner)
    if action == "menu":
        text = "📋 <b>Меню</b>"
    elif action == "profile":
        text = views.profile_text(user, is_admin=user["is_admin"] or user["id"] in settings.owner_ids)
    elif action == "help":
        text = f'<a href="{views.HELP_URL}">Список команд</a>'
    else:
        async with pool.acquire() as con:
            code = await referral.get_or_create_code(con, user["id"])
            used = await referral.uses_count(con, user["id"])
        link = f"https://t.me/{settings.bot_username}?start={code}"
        text = (
            f"🎁 Ваш реферальный код: <code>{code}</code>\nАктивирован раз: <code>{used}</code>\n\n"
            f"{esc(link)}\nПриглашайте людей и получайте по 20 коинов за человека."
        )
    if call.message:
        try:
            await call.message.edit_text(text, reply_markup=markup)
        except TelegramAPIError:
            pass
    await call.answer()
