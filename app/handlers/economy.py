"""Balance, farm, transfers, donations and the personal ledger history."""
from __future__ import annotations

import json
import logging
import random
import secrets
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import constants
from app.db import actions, history, ledger, users
from app.middlewares import RequireUser
from app.services import keyboards
from app.services.action_registry import action_handler
from app.utils.filters import Trigger
from app.utils.money import coin_form, fmt, fmt_money, parse_amount, quantize
from app.utils.telegram import safe_edit
from app.utils.text import args_of, esc, mention, raw_args
from app.utils.timeutils import fmt_datetime, human_duration

logger = logging.getLogger(__name__)

router = Router(name="economy")                 # commands that work without registration
registered = Router(name="economy-registered")  # commands that need an account
registered.message.middleware(RequireUser())
registered.callback_query.middleware(RequireUser())
router.include_router(registered)

FARM_ALIASES = ("farm", "farma", "фарм", "заработать", "поработать", "работа", "добыть", "нафармить")
PAY_ALIASES = ("pay", "перевести", "перевод", "скинуть", "перекинуть")


# ---- balance ---------------------------------------------------------------
@registered.message(Command("money", "balance", "баланс", "бал"))
@registered.message(Trigger("баланс", "бал"))
async def cmd_balance(message: Message, bot: Bot, user, settings) -> None:
    money = quantize(user["balance"])
    text = f"💰 Ваш баланс: {fmt(money)} {coin_form(money)}."
    if user["hide_balance"]:
        try:
            await bot.send_message(user["id"], text)
            link = f'<a href="https://t.me/{settings.bot_username}">ЛС</a>'
            await message.reply(f"💰 Смотрите баланс в {link}")
        except TelegramAPIError:
            await message.reply("❌ Не удалось отправить баланс в ЛС. Напишите боту /start.")
        return
    last_farm = user["last_farm_at"]
    farm_ready = last_farm is None or (datetime.now(timezone.utc) - last_farm).total_seconds() > constants.FARM_COOLDOWN
    if farm_ready and money <= constants.FARM_MAX_BALANCE:
        text += "\n\nВведите /farm для фарма коинов!"
    await message.reply(text)


# ---- farm ------------------------------------------------------------------
@registered.message(Command("farm"))
@registered.message(Trigger(*FARM_ALIASES))
async def cmd_farm(message: Message, pool, user) -> None:
    uid = user["id"]
    code = ledger.user_code(uid)
    amount = quantize(secrets.choice(range(*constants.FARM_RANGE_CENTS)) / 100)
    lucky = random.random() < constants.FARM_MULTI_CHANCE
    if lucky:
        amount = quantize(amount * constants.FARM_MULTI)

    async with pool.acquire() as con:
        async with con.transaction():
            balance = await ledger.balance(con, code)
            if balance > constants.FARM_MAX_BALANCE:
                await message.reply(
                    f"❌ Фармить можно только если баланс не больше {fmt(constants.FARM_MAX_BALANCE)} коинов!"
                )
                return
            if await ledger.balance(con, ledger.BANK) < constants.FARM_MIN_BANK:
                await message.reply("Недостаточно средств на балансе банка.")
                return
            claimed = await con.fetchrow(
                "UPDATE users SET last_farm_at = now() WHERE id = $1 AND (last_farm_at IS NULL OR "
                "last_farm_at <= now() - make_interval(secs => $2)) RETURNING last_farm_at",
                uid, float(constants.FARM_COOLDOWN),
            )
            if claimed is None:
                last = await con.fetchval("SELECT EXTRACT(EPOCH FROM now() - last_farm_at)::float FROM users WHERE id = $1", uid)
                left = constants.FARM_COOLDOWN - (last or 0)
                await message.reply(f"❌ <b>Рано!</b>\n\n⏳ До фарма осталось {human_duration(left)}.")
                return
            try:
                await ledger.post(con, "farm", {ledger.BANK: -amount, code: amount}, initiator_id=uid,
                                  meta={"lucky": lucky})
            except ledger.InsufficientFunds:
                await message.reply("Недостаточно средств на балансе банка.")
                return
            new_balance = await ledger.balance(con, code)

    title = "✅ <b>Удача на вашей стороне!</b>" if lucky else "✅ <b>Успешно!</b>"
    multi = f" ({constants.FARM_MULTI}x)" if lucky else ""
    text = f"{title}\n\nВы нафармили {fmt(amount)}{multi} {coin_form(amount)}."
    if user["hide_balance"]:
        text += " Смотрите баланс с помощью команды /money"
    else:
        text += f"\nВаш баланс: {fmt(new_balance)} {coin_form(new_balance)}"
    await message.reply(text)


# ---- bank / donate ---------------------------------------------------------
@router.message(Command("bank"))
async def cmd_bank(message: Message, pool) -> None:
    async with pool.acquire() as con:
        bank = await ledger.balance(con, ledger.BANK)
    await message.reply(f"🏦 Денег в банке: {fmt_money(bank)}")


@registered.message(Command("donate"))
async def cmd_donate(message: Message, pool, user) -> None:
    tokens = args_of(message)
    if len(tokens) != 1:
        await message.reply("Пожертвуйте несколько коинов в банк!\n\nИспользование: <code>/donate сумма</code>")
        return
    amount = parse_amount(tokens[0], all_value=user["balance"])
    if amount is None:
        await message.reply("Пожалуйста, введите сумму коинов для пожертвования.")
        return
    if amount < constants.MIN_DONATE:
        await message.reply("Сумма должна быть больше или равна 1 коину")
        return
    try:
        async with pool.acquire() as con:
            await ledger.post(con, "donation", {ledger.user_code(user["id"]): -amount, ledger.BANK: amount},
                              initiator_id=user["id"])
    except ledger.InsufficientFunds:
        await message.reply("У вас недостаточно средств! Посмотрите свой баланс с помощью команды /money")
        return
    await message.reply(f"Вы успешно пожертвовали {fmt_money(amount)} в банк!")


# ---- transfers -------------------------------------------------------------
@registered.message(Command("pay"))
@registered.message(Trigger(*PAY_ALIASES, with_args=True))
async def cmd_pay(message: Message, pool, user) -> None:
    tokens = args_of(message)
    reply = message.reply_to_message
    usage = "❌ Неверные аргументы!\n\nПример:\n/pay @username 1.25 комментарий\nИли ответом на сообщение: /pay 1.25"
    if not tokens:
        await message.reply(usage)
        return

    target_token: str | None = None
    amount: Decimal | None = None
    comment_tokens: list[str] = []
    if reply and reply.from_user and not reply.from_user.is_bot:
        amount = parse_amount(tokens[0], all_value=user["balance"])
        if amount is not None:
            target_token = str(reply.from_user.id)
            comment_tokens = tokens[1:]
    if amount is None:
        if len(tokens) < 2:
            await message.reply(usage)
            return
        target_token = tokens[0]
        amount = parse_amount(tokens[1], all_value=user["balance"])
        comment_tokens = tokens[2:]
    if amount is None:
        await message.reply("❌ Сумма должна быть числом.")
        return
    if amount < constants.MIN_AMOUNT_PAY:
        await message.reply(f"❌ Сумма перевода не может быть меньше {fmt(constants.MIN_AMOUNT_PAY)} {coin_form(constants.MIN_AMOUNT_PAY)}!")
        return

    async with pool.acquire() as con:
        target = await users.find(con, target_token or "")
        if target is None:
            await message.reply("❌ Пользователь не найден!")
            return
        if target["id"] == user["id"]:
            await message.reply("❌ Невозможно перевести коины самому себе!")
            return
        if quantize(user["balance"]) < amount:
            await message.reply("❌ Недостаточно средств!")
            return
        comment = " ".join(comment_tokens)[:200] or None
        action_id = await actions.create(
            con, "pay", user["id"],
            {"to": target["id"], "amount": str(amount), "comment": comment, "chat_id": message.chat.id},
            message.chat.id,
        )
    commission = quantize(amount * constants.COMMISSION_PAY / 100)
    await message.reply(
        f"Подтвердите перевод <b>{fmt_money(amount)}</b> пользователю {esc(target['name'])}.\n"
        f"Комиссия: {fmt_money(commission)} ({fmt(constants.COMMISSION_PAY)}%).",
        reply_markup=keyboards.confirm_kb(action_id),
    )


@action_handler("pay")
async def confirm_pay(call: CallbackQuery, action, *, pool, bot: Bot, **_) -> None:
    payload = action["payload"]
    sender_id, target_id = action["owner_id"], payload["to"]
    amount = Decimal(payload["amount"])
    commission = quantize(amount * constants.COMMISSION_PAY / 100)
    received = amount - commission
    try:
        async with pool.acquire() as con:
            async with con.transaction():
                sender = await users.get(con, sender_id)
                target = await users.get(con, target_id)
                if not target or not sender:
                    await safe_edit(call, "❌ Получатель или отправитель больше не зарегистрирован.")
                    await call.answer()
                    return
                tx_id = await ledger.post(
                    con, "transfer",
                    {ledger.user_code(sender_id): -amount, ledger.user_code(target_id): received, ledger.BANK: commission},
                    initiator_id=sender_id, comment=payload.get("comment"),
                    meta={"commission": str(commission), "percent": str(constants.COMMISSION_PAY),
                          "chat_id": payload.get("chat_id")},
                )
    except ledger.InsufficientFunds:
        await safe_edit(call, "❌ Недостаточно средств!")
        await call.answer()
        return

    logger.info("Transfer %s: %s -> %s, amount=%s", tx_id, sender_id, target_id, amount)
    await safe_edit(call, f"✅ <b>Перевод выполнен!</b>\n\nUUID: <code>{tx_id}</code>")
    await call.answer()

    when = fmt_datetime(datetime.now(timezone.utc))
    comment = f"\nКомментарий: {esc(payload['comment'])}" if payload.get("comment") else ""
    if sender["transfer_check"]:
        who = f"{esc(target['name'])}" + (f" (@{esc(target['username'])})" if target["username"] and not target["hide_username"] else "")
        await _try_send(bot, sender_id,
            f"✅ <b>Успешный перевод</b>\n\nПолучатель: {who}\nСписано: {fmt_money(amount)}\n"
            f"Комиссия: {fmt_money(commission)}{comment}\nДата (МСК): {when}\nUUID: <code>{tx_id}</code>")
    if target["transfer_check"]:
        who = f"{esc(sender['name'])}" + (f" (@{esc(sender['username'])})" if sender["username"] and not sender["hide_username"] else "")
        await _try_send(bot, target_id,
            f"💰 <b>Вам перевели коины</b>\n\nОтправитель: {who}\nПолучено: {fmt_money(received)}"
            f"{comment}\nДата (МСК): {when}\nUUID: <code>{tx_id}</code>")


async def _try_send(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except TelegramAPIError as exc:
        logger.info("Could not send a message to %s: %s", chat_id, exc)


def _mask(code: str) -> str:
    return f"user:{code[5:9]}…" if code.startswith("user:") else code


@router.message(Command("show_transaction"))
async def cmd_show_transaction(message: Message, pool) -> None:
    value = raw_args(message).strip()
    if not value:
        await message.reply("Введите после команды UUID транзакции.")
        return
    async with pool.acquire() as con:
        tx, entries = await history.transaction(con, value)
    if tx is None:
        await message.reply("Транзакции не существует.")
        return
    body = {
        "kind": tx["kind"],
        "created_at": tx["created_at"].isoformat(),
        "comment": tx["comment"],
        "entries": [{"account": _mask(e["code"]), "amount": str(e["amount"])} for e in entries],
    }
    await message.reply(f"Транзакция <code>{tx['id']}</code>:\n\n<pre>{esc(json.dumps(body, indent=2, ensure_ascii=False))}</pre>")


@registered.message(Command("my_transaction"))
async def cmd_my_transactions(message: Message, bot: Bot, pool, user) -> None:
    async with pool.acquire() as con:
        summary = await history.transfer_summary(con, user["id"])
    lines = [
        "<b>Ваши переводы</b>\n",
        f"Общий доход: <code>{fmt(summary['income'])}</code>",
        f"Общий расход: <code>{fmt(summary['outcome'])}</code>",
        f"Итог: <code>{fmt(summary['income'] - summary['outcome'])}</code>\n",
        "Доход (последние 15):",
        *[f"{i}. <code>{t}</code>" for i, t in enumerate(summary["incoming"], 1)],
        "\nРасход (последние 15):",
        *[f"{i}. <code>{t}</code>" for i, t in enumerate(summary["outgoing"], 1)],
    ]
    try:
        await bot.send_message(user["id"], "\n".join(lines))
        if message.chat.id != user["id"]:
            await message.reply("📬 Отправил в личные сообщения.")
    except TelegramAPIError:
        await message.reply("❌ Не удалось отправить в ЛС. Напишите боту /start.")


@registered.message(Command("log", "logs"))
async def cmd_logs(message: Message, bot: Bot, pool, user, settings) -> None:
    tokens = args_of(message)
    target = user
    if tokens and user["id"] in settings.owner_ids and tokens[0].isdigit():
        async with pool.acquire() as con:
            found = await users.find(con, tokens[0])
        if found is None:
            await message.reply("Пользователь не найден.")
            return
        target = found
    async with pool.acquire() as con:
        entries = await history.user_entries(con, target["id"], 30)
    if not entries:
        text = "Empty..."
    else:
        text = "\n".join(
            f"{fmt_datetime(e['created_at'])} {e['kind']} {'+' if e['amount'] > 0 else ''}{fmt(e['amount'])} → {fmt(e['balance_after'])}"
            for e in entries
        )
    try:
        await bot.send_message(user["id"], f"Последние операции {esc(target['name'])}\n\n<blockquote expandable>{esc(text)}</blockquote>")
    except TelegramAPIError:
        await message.reply("❌ Не удалось отправить в ЛС. Напишите боту /start.")


@router.message(Command("credit", "my_credit", "pay_credit", "dolg"))
async def cmd_credit_blocked(message: Message) -> None:
    await message.reply("❌ <b>Кредит заблокирован!</b>")
