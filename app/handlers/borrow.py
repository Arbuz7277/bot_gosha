"""Peer-to-peer loans: /borrow creates a request, /borrow+ accepts it."""
from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app import constants
from app.db import borrow, ledger, users
from app.middlewares import RequireUser
from app.utils.money import fmt, fmt_money, parse_amount, quantize
from app.utils.text import args_of, esc, mention

logger = logging.getLogger(__name__)

router = Router(name="borrow")
router.message.middleware(RequireUser())


@router.message(Command("borrow"))
async def cmd_borrow(message: Message, pool, user) -> None:
    tokens = args_of(message)
    if len(tokens) != 4:
        await message.reply("Используйте: <code>/borrow &lt;сумма&gt; &lt;срок в часах&gt; &lt;процент&gt; &lt;юзернейм|id&gt;</code>")
        return
    amount = parse_amount(tokens[0])
    if amount is None or not tokens[1].isdigit() or not tokens[2].isdigit():
        await message.reply("<b>Вы ввели неверные данные!</b> Сумма, срок и процент должны быть числами.")
        return
    term, percent = int(tokens[1]), int(tokens[2])
    checks = (
        (amount < constants.MIN_AMOUNT_BORROW, f"Сумма не может быть меньше {fmt(constants.MIN_AMOUNT_BORROW)}!"),
        (amount > constants.MAX_AMOUNT_BORROW, f"Сумма не может быть больше {fmt(constants.MAX_AMOUNT_BORROW)}!"),
        (term < constants.MIN_TERM_BORROW, f"Срок не может быть меньше {constants.MIN_TERM_BORROW} ч!"),
        (term > constants.MAX_TERM_BORROW, f"Срок не может быть больше {constants.MAX_TERM_BORROW} ч!"),
        (percent < constants.MIN_PERCENT_BORROW, f"Процент не может быть меньше {constants.MIN_PERCENT_BORROW}%!"),
        (percent > constants.MAX_PERCENT_BORROW, f"Процент не может быть больше {constants.MAX_PERCENT_BORROW}%!"),
    )
    for failed, text in checks:
        if failed:
            await message.reply(f"<b>{text}</b>")
            return
    if quantize(user["balance"]) < 0:
        await message.reply("<b>Брать долг невозможно, имея отрицательный баланс!</b>")
        return

    async with pool.acquire() as con:
        lender = await users.find(con, tokens[3])
        if lender is None:
            await message.reply("<b>Пользователь не найден!</b>")
            return
        if lender["id"] == user["id"]:
            await message.reply("<b>Невозможно взять в долг у самого себя.</b>")
            return
        if quantize(lender["balance"]) < amount:
            await message.reply("<b>У пользователя недостаточно средств!</b>")
            return
        request_id = await borrow.create_request(con, user["id"], lender["id"], amount, percent, term)
    if request_id is None:
        await message.reply("<b>Вы уже отправили этому пользователю запрос!</b>")
        return
    due = borrow.amount_due(amount, percent)
    await message.answer(
        f"{mention(lender['id'], lender['name'])}, у вас хотят взять в долг {fmt_money(amount)} на срок {term} ч. "
        f"под {percent}%. После истечения срока вы получите обратно {fmt_money(due)}.\n"
        f"Если вы согласны, введите команду <code>/borrow+ {user['id']}</code>"
    )


@router.message(Command("borrow+"))
async def cmd_borrow_accept(message: Message, pool, user) -> None:
    tokens = args_of(message)
    if len(tokens) != 1 or not tokens[0].isdigit():
        await message.reply("<b>Укажите id заёмщика:</b> <code>/borrow+ &lt;id&gt;</code>")
        return
    borrower_id = int(tokens[0])
    try:
        async with pool.acquire() as con:
            loan = await borrow.accept(con, borrower_id, user["id"])
            borrower = await users.get(con, borrower_id)
    except ledger.InsufficientFunds:
        await message.reply("<b>У вас недостаточно средств!</b>")
        return
    if loan is None or borrower is None:
        await message.reply("<b>Предложение не найдено!</b>")
        return
    logger.info("Loan %s issued: lender=%s borrower=%s amount=%s", loan["id"], user["id"], borrower_id, loan["amount"])
    await message.reply(
        f"<b>Успешно!</b> Вы выдали {fmt_money(loan['amount'])} пользователю {esc(borrower['name'])} "
        f"на {loan['term_hours']} ч.\nПосле истечения срока {fmt_money(loan['amount_due'])} вернутся автоматически."
    )
