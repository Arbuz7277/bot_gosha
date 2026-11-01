"""Small stateless commands."""
from __future__ import annotations

import hashlib
import logging
import random
import time
from datetime import datetime, timezone

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message

from app import constants
from app.constants import EMAIL, GITHUB
from app.db import users
from app.utils import calc
from app.utils.filters import IsOwner, Trigger
from app.utils.text import args_of, esc, raw_args
from app.utils.timeutils import fmt_datetime

logger = logging.getLogger(__name__)

router = Router(name="utility")



@router.message(Command("ping"))
async def cmd_ping(message: Message, bot: Bot) -> None:
    started = time.perf_counter()
    await bot.get_me()
    ping = int((time.perf_counter() - started) * 1000)
    await message.reply(f"✨ Ping: {ping} ms\n🕒 UTC: {datetime.now(timezone.utc).replace(microsecond=0)}")


@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    await message.reply(f"Email: {EMAIL}\nGitHub: <a href=\"{GITHUB}\">repo</a>")


@router.message(Command("version"))
@router.message(Trigger("version", "версия"))
async def cmd_version(message: Message) -> None:
    await message.reply(f"Version: {constants.VERSION}")


@router.message(Command("id"))
async def cmd_id(message: Message, pool) -> None:
    target = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    async with pool.acquire() as con:
        found = await users.get(con, target.id)
    gid = found["gid"] if found else "—"
    await message.reply(f"Telegram ID: <code>{target.id}</code>\nGosha ID: <code>{gid}</code>")


@router.message(Command("id_chat"))
async def cmd_id_chat(message: Message) -> None:
    await message.reply(f"ID chat: <code>{message.chat.id}</code>")


@router.message(Command("info"))
async def cmd_info(message: Message, bot: Bot) -> None:
    chat = message.chat
    lines = [f"Chat_id: {chat.id}", f"Chat_type: {chat.type}"]
    try:
        full = await bot.get_chat(chat.id)
    except TelegramAPIError:
        full = None
    if chat.type == "private":
        lines += [f"First name: {esc(chat.first_name)}", f"Last name: {esc(chat.last_name)}",
                  f"Username: {esc(chat.username)}", f"Bio: {esc(getattr(full, 'bio', None))}"]
    else:
        lines = [f"Name: {esc(chat.title)}", *lines,
                 f"Description: {esc(getattr(full, 'description', None))}",
                 f"Link: {esc(getattr(full, 'invite_link', None))}"]
    await message.reply("\n".join(lines))


@router.message(Command("random"))
async def cmd_random(message: Message) -> None:
    tokens = args_of(message)
    if len(tokens) not in (2, 3):
        await message.reply("Использование: <code>/random &lt;от&gt; &lt;до&gt; [сколько уникальных]</code>")
        return
    try:
        low, high = int(tokens[0]), int(tokens[1])
        count = int(tokens[2]) if len(tokens) == 3 else 1
    except ValueError:
        await message.reply("Enter numbers!")
        return
    if low > high or abs(low) > 1000 or abs(high) > 1000 or not 1 <= count <= 100 or count > high - low + 1:
        await message.reply("Числа должны быть в диапазоне от -1000 до 1000, от ≤ до, количество от 1 до 100.")
        return
    if len(tokens) == 3:
        await message.reply("Numbers: " + ", ".join(map(str, random.sample(range(low, high + 1), count))))
    else:
        await message.reply(f"Number: {random.randint(low, high)}")


@router.message(Command("ball"))
async def cmd_ball(message: Message) -> None:
    await message.reply(f"{random.choice(constants.BALL_VARIABLES)}{esc(raw_args(message).strip())}")


@router.message(Command("answer"))
async def cmd_answer(message: Message) -> None:
    expression = raw_args(message)
    try:
        result = calc.format_result(calc.safe_calc(expression))
    except calc.CalcError as exc:
        await message.reply(f"Error! {esc(exc)}")
        return
    await message.reply(f"Example: <code>{esc(expression.strip())}</code>\n\nAnswer: <code>{result}</code>")


@router.message(Command("time"))
async def cmd_time(message: Message) -> None:
    await message.reply(f"Точное время по МСК: <code>{fmt_datetime(datetime.now(timezone.utc))}</code>")


@router.message(Command("search_id"))
async def cmd_search_id(message: Message) -> None:
    tokens = args_of(message)
    if len(tokens) != 1 or not tokens[0].isdigit():
        return
    await message.reply(f'URL: <a href="tg://user?id={tokens[0]}">{tokens[0]}</a>')


@router.message(Command("sha256"))
async def cmd_sha256(message: Message) -> None:
    text = raw_args(message).strip()
    if not text:
        await message.reply("Использование: <code>/sha256 текст</code>")
        return
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    await message.reply(f"Текст: <code>{esc(text)}</code>\nКодировка: <code>utf-8</code>\n\nSHA256: <code>{digest}</code>")


@router.message(Command("sha256hex"))
async def cmd_sha256hex(message: Message) -> None:
    text = raw_args(message).strip()
    try:
        digest = hashlib.sha256(bytes.fromhex(text)).hexdigest()
    except ValueError:
        await message.reply("Введите корректную hex-строку, например <code>/sha256hex 68656c6c6f</code>")
        return
    await message.reply(f"Hex: <code>{esc(text)}</code>\n\nSHA256: <code>{digest}</code>")


@router.message(Command("user_info"))
async def cmd_user_info(message: Message) -> None:
    target = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    info = target.model_dump(mode="json", exclude_none=not any(a in ("-a", "--all") for a in args_of(message)))
    flags = args_of(message)
    if "-j" in flags or "--json" in flags:
        import json
        await message.reply(f"<pre>{esc(json.dumps(info, indent=2, ensure_ascii=False))}</pre>")
        return
    await message.reply("\n".join(f"{i}. {esc(k)}: {esc(v)}" for i, (k, v) in enumerate(info.items(), 1)) or "Empty")


@router.message(Command("message", "msg"))
async def cmd_message(message: Message) -> None:
    body = message.model_dump_json(exclude_none=True, indent=2)
    await message.reply(f"<pre>{esc(body[:3500])}</pre>")


@router.message(Command("uptime"), IsOwner())
async def cmd_uptime(message: Message, runtime) -> None:
    try:
        with open("/proc/uptime", encoding="utf-8") as f:
            seconds = float(f.readline().split()[0])
        label = "System"
    except OSError:
        seconds = time.time() - runtime.started_at
        label = "Bot"
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    await message.reply(f"{label} uptime: {days} days, {hours:02d}:{minutes:02d}:{secs:02d}")
