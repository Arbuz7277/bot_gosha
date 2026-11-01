"""Group chat tools: mute/unmute, join/leave greetings, roleplay and small text triggers."""
from __future__ import annotations

import logging
import random
from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import ChatPermissions, Message

from app import constants
from app.db import chats, users
from app.utils.filters import Trigger
from app.utils.telegram import is_chat_admin
from app.utils.text import args_of, esc, mention, raw_args
from app.utils.timeutils import parse_duration

logger = logging.getLogger(__name__)

router = Router(name="chat-tools")

NO_PERMISSIONS = ChatPermissions(
    can_send_messages=False, can_send_audios=False, can_send_documents=False, can_send_photos=False,
    can_send_videos=False, can_send_video_notes=False, can_send_voice_notes=False, can_send_polls=False,
    can_send_other_messages=False, can_add_web_page_previews=False,
)
ALL_PERMISSIONS = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True,
    can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True,
    can_send_other_messages=True, can_add_web_page_previews=True,
)


@router.message(Command("mute"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_mute(message: Message, bot: Bot) -> None:
    if not await is_chat_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("Вы не администратор!")
        return
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if target is None:
        await message.reply("Ответьте на сообщение пользователя, которого нужно замутить!")
        return
    tokens = args_of(message)
    minutes = parse_duration(tokens[0]) if tokens else None
    if minutes is None:
        await message.reply("Укажите время: <code>/mute 30m причина</code> (m — минуты, h — часы, d — дни, w — недели).")
        return
    reason = " ".join(tokens[1:])
    if await is_chat_admin(bot, message.chat.id, target.id):
        await message.reply("Нельзя замутить администратора.")
        return
    try:
        await bot.restrict_chat_member(message.chat.id, target.id, permissions=NO_PERMISSIONS,
                                       until_date=timedelta(minutes=minutes))
    except TelegramAPIError as exc:
        logger.warning("mute failed chat=%s target=%s: %s", message.chat.id, target.id, exc)
        await message.reply(f"Произошла ошибка. Проверьте права бота.\n\n{esc(exc)}")
        return
    logger.info("User %s muted %s in chat %s for %d min", message.from_user.id, target.id, message.chat.id, minutes)
    text = f"Успешно!\n\nПользователь {esc(target.first_name)} замучен на {minutes} мин."
    if reason:
        text += f"\n\nПричина: {esc(reason)}"
    await message.reply(text)


@router.message(Command("unmute"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_unmute(message: Message, bot: Bot) -> None:
    if not await is_chat_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("Вы не администратор!")
        return
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if target is None:
        await message.reply("Ответьте на сообщение пользователя!")
        return
    try:
        chat = await bot.get_chat(message.chat.id)
        await bot.restrict_chat_member(message.chat.id, target.id, permissions=chat.permissions or ALL_PERMISSIONS)
    except TelegramAPIError as exc:
        await message.reply(f"Произошла ошибка.\n\n{esc(exc)}")
        return
    await message.reply(f"Успешно!\n\nПользователь {esc(target.first_name)} размучен!")


@router.message(F.new_chat_members)
async def on_new_members(message: Message, bot: Bot, pool) -> None:
    me = await bot.me()
    for member in message.new_chat_members or []:
        if member.id == me.id:
            await message.reply("Я рад, что вы меня добавили в чат 😊\nИспользуйте /help для просмотра моих команд")
            return
        async with pool.acquire() as con:
            found = await users.get(con, member.id)
            if found:
                await chats.add_member(con, member.id, message.chat.id)
        if found:
            await message.reply(f"Привет, <b>{esc(member.first_name)}</b>!")


@router.message(F.left_chat_member)
async def on_left_member(message: Message, pool) -> None:
    member = message.left_chat_member
    async with pool.acquire() as con:
        removed = await chats.remove_member(con, member.id, message.chat.id)
    if removed:
        await message.reply(f"Пока, <b>{esc(member.first_name)}</b> :(")


@router.message(Command("me", "m"))
async def cmd_rp_me(message: Message, bot: Bot, pool) -> None:
    text = raw_args(message).strip()[:512]
    if not text:
        return
    async with pool.acquire() as con:
        found = await users.get(con, message.from_user.id)
    name = found["name"] if found else message.from_user.first_name
    try:
        await message.delete()
    except TelegramAPIError:
        pass
    await message.answer(f"{mention(message.from_user.id, name)} {esc(text)}")


@router.message(Trigger("бот", "гоша", "долбоеб"))
async def reply_to_name(message: Message) -> None:
    await message.reply(f"<b>{random.choice(constants.MESSAGE_GOSHA)}</b>")


@router.message(Trigger("шип"))
async def cmd_ship(message: Message, pool) -> None:
    if message.chat.type == ChatType.PRIVATE:
        await message.reply("Это не группа!")
        return
    async with pool.acquire() as con:
        members = await chats.member_names(con, message.chat.id)
    if len(members) < 2:
        await message.reply("Нужно как минимум 2 пользователя в чате!")
        return
    first, second = random.sample(list(members), 2)
    await message.reply(f"Рандом шип\n\n{mention(first['id'], first['name'])} и {mention(second['id'], second['name'])}")
