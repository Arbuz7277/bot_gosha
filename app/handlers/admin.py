"""Owner / admin commands."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import Message

from app.db import chats, ledger, quotes, shop, stats, users
from app.utils.filters import IsAdmin, IsOwner
from app.utils.money import coin_form, fmt, fmt_money, parse_amount, quantize
from app.utils.text import args_of, esc, raw_args
from app.utils.timeutils import fmt_datetime

logger = logging.getLogger(__name__)

owner_router = Router(name="admin-owner")
owner_router.message.filter(IsOwner())
admin_router = Router(name="admin-staff")
admin_router.message.filter(IsAdmin())

router = Router(name="admin")
router.include_router(owner_router)
router.include_router(admin_router)


async def _reply_target(message: Message, pool) -> tuple | None:
    """Registered user the command message replies to."""
    reply = message.reply_to_message
    if reply is None or reply.from_user is None:
        await message.reply("❌ Ответьте на сообщение пользователя.")
        return None
    async with pool.acquire() as con:
        found = await users.get(con, reply.from_user.id)
    if found is None:
        await message.reply("❌ Пользователь не зарегистрирован!\n\nДля регистрации введите /start")
        return None
    return (found,)


@owner_router.message(Command("add_admin"))
async def cmd_add_admin(message: Message, pool) -> None:
    target = await _reply_target(message, pool)
    if not target:
        return
    (found,) = target
    if found["is_admin"]:
        await message.reply(f"❌ Ошибка!\n\n{esc(found['name'])} уже админ.")
        return
    async with pool.acquire() as con:
        await users.set_admin(con, found["id"], True)
    logger.info("Owner %s granted admin to %s", message.from_user.id, found["id"])
    await message.reply(f"✅ Успешно!\n\n{esc(found['name'])} получил админку.")


@owner_router.message(Command("remove_admin"))
async def cmd_remove_admin(message: Message, pool) -> None:
    target = await _reply_target(message, pool)
    if not target:
        return
    (found,) = target
    if not found["is_admin"]:
        await message.reply(f"❌ Ошибка!\n\n{esc(found['name'])} и так не админ.")
        return
    async with pool.acquire() as con:
        await users.set_admin(con, found["id"], False)
    logger.info("Owner %s revoked admin from %s", message.from_user.id, found["id"])
    await message.reply(f"✅ Успешно!\n\nАдминка у {esc(found['name'])} удалена.")


@owner_router.message(Command("set_money"))
async def cmd_set_money(message: Message, pool) -> None:
    target = await _reply_target(message, pool)
    if not target:
        return
    (found,) = target
    tokens = args_of(message)
    amount = parse_amount(tokens[0]) if tokens else None
    if amount is None:
        await message.reply("❌ Введите число!")
        return
    code = ledger.user_code(found["id"])
    async with pool.acquire() as con:
        async with con.transaction():
            current = await ledger.balance(con, code)
            delta = amount - current
            if delta != 0:
                await ledger.post(con, "admin_set_money", {code: delta, ledger.EMISSION: -delta},
                                  initiator_id=message.from_user.id, comment=f"set to {amount}")
    logger.warning("Owner %s set balance of %s to %s", message.from_user.id, found["id"], amount)
    await message.reply(f"✅ Успешно!\n\nУ пользователя {esc(found['name'])} теперь {fmt_money(amount)}!")


@owner_router.message(Command("econ"))
async def cmd_econ(message: Message, pool) -> None:
    async with pool.acquire() as con:
        bank = await ledger.balance(con, ledger.BANK)
        total_users, count = await stats.users_money(con)
    result = bank + total_users
    await message.reply(f"Всего: {fmt_money(result)}\nБанк: {fmt(bank)}\nУ пользователей ({count}): {fmt(total_users)}")


@owner_router.message(Command("stats"))
async def cmd_stats(message: Message, bot: Bot, pool) -> None:
    started = time.perf_counter()
    await bot.get_me()
    ping = int((time.perf_counter() - started) * 1000)
    async with pool.acquire() as con:
        bank = await ledger.balance(con, ledger.BANK)
        users_total, count = await stats.users_money(con)
    econ = bank + users_total
    share = lambda x: int(x / econ * 100) if econ else 0  # noqa: E731
    await message.reply(
        f"UTC: {datetime.now(timezone.utc).replace(microsecond=0)}\nPing: {ping}ms\n\n"
        f"Bank: {fmt(bank)} coins ({share(bank)}%)\nUsers money: {fmt(users_total)} coins ({share(users_total)}%)\n"
        f"Users: {count}\nEconomy: {fmt(econ)} coins"
    )


@owner_router.message(Command("audit"))
async def cmd_audit(message: Message, pool) -> None:
    repair = "repair" in args_of(message)
    async with pool.acquire() as con:
        report = await ledger.reconcile(con, repair=repair)
    ok = not report["mismatches"] and not report["unbalanced"] and report["ledger_sum"] == 0
    lines = [f"{'✅' if ok else '⚠️'} Ledger audit", f"Global ledger sum: {report['ledger_sum']}",
             f"Unbalanced transactions: {len(report['unbalanced'])}",
             f"Cached balance mismatches: {len(report['mismatches'])}"]
    for row in report["mismatches"][:10]:
        lines.append(f"• {esc(row['code'])}: cache {row['cached']} / ledger {row['ledger']}")
    if report["repaired"]:
        lines.append("🔧 Cached balances were rebuilt from the ledger.")
    elif report["mismatches"]:
        lines.append("Run <code>/audit repair</code> to rebuild the cache.")
    await message.reply("\n".join(lines))


@owner_router.message(Command("maintenance"))
async def cmd_maintenance(message: Message, runtime) -> None:
    tokens = args_of(message)
    if not tokens or tokens[0].lower() not in ("on", "off"):
        await message.reply(f"Maintenance: {'on' if runtime.maintenance else 'off'}\nИспользование: /maintenance on|off")
        return
    runtime.maintenance = tokens[0].lower() == "on"
    logger.warning("Maintenance mode %s", "enabled" if runtime.maintenance else "disabled")
    await message.reply(f"Maintenance: {'on' if runtime.maintenance else 'off'}")


@owner_router.message(Command("ad"))
async def cmd_ad(message: Message, bot: Bot, pool) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3 or parts[1].lower() not in ("pin", "not_pin"):
        await message.reply("Использование: <code>/ad pin|not_pin текст (HTML)</code>")
        return
    pin, text = parts[1].lower() == "pin", parts[2]
    async with pool.acquire() as con:
        targets = await chats.all_chat_ids(con)
    await message.reply(f"Доставка сообщения в {len(targets)} чатов...")
    delivered = blocked = failed = 0
    for chat_id in targets:
        try:
            sent = await bot.send_message(chat_id, text)
            if pin:
                try:
                    await bot.pin_chat_message(chat_id, sent.message_id)
                except TelegramAPIError:
                    pass
            delivered += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            failed += 1
        except TelegramAPIError as exc:
            if "blocked" in str(exc).lower() or "deactivated" in str(exc).lower() or "kicked" in str(exc).lower():
                blocked += 1
            else:
                failed += 1
        await asyncio.sleep(0.05)
    logger.info("Broadcast finished: delivered=%d blocked=%d failed=%d", delivered, blocked, failed)
    await message.reply(f"✅ Закончено!\n\nДоставлено: {delivered}\nЗаблокировано: {blocked}\nОшибок: {failed}")


@owner_router.message(Command("send"))
async def cmd_send(message: Message, bot: Bot) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3 or not parts[1].lstrip("-").isdigit():
        await message.reply("Использование: <code>/send &lt;chat_id&gt; &lt;текст&gt;</code>")
        return
    try:
        await bot.send_message(int(parts[1]), parts[2])
    except TelegramAPIError as exc:
        await message.reply(f"❌ {esc(exc)}")
        return
    await message.reply("✅ Отправлено")


@owner_router.message(Command("shop_add"))
async def cmd_shop_add(message: Message, pool) -> None:
    parts = [p.strip() for p in raw_args(message).split("|")]
    price = parse_amount(parts[2]) if len(parts) == 3 else None
    if len(parts) != 3 or not parts[0] or not parts[1] or price is None or price <= 0:
        await message.reply("Использование: <code>/shop_add категория | товар | цена</code>")
        return
    async with pool.acquire() as con:
        item_id = await shop.add_item(con, parts[0][:64], parts[1][:64], price)
    await message.reply(f"✅ Товар #{item_id} добавлен.")


@admin_router.message(Command("all_money"))
async def cmd_all_money(message: Message, pool) -> None:
    async with pool.acquire() as con:
        total, _ = await stats.users_money(con)
    await message.reply(f"Всего у пользователей: {fmt_money(total)}")


@admin_router.message(Command("users"))
async def cmd_users(message: Message, pool) -> None:
    async with pool.acquire() as con:
        count = await users.count(con)
    await message.reply(f"Всего пользователей: {count}")


@admin_router.message(Command("qverify", "qdel"))
async def cmd_quote_moderation(message: Message, pool) -> None:
    tokens = args_of(message)
    command = (message.text or "").split()[0].lower()
    if len(tokens) != 1 or not tokens[0].isdigit():
        await message.reply("Использование: <code>/qverify &lt;id&gt;</code> или <code>/qdel &lt;id&gt;</code>")
        return
    quote_id = int(tokens[0])
    async with pool.acquire() as con:
        if command.startswith("/qdel"):
            done = await quotes.delete(con, quote_id)
        else:
            done = await quotes.set_verified(con, quote_id, True)
    await message.reply("✅ Готово." if done else "❌ Цитата не найдена.")
