"""Casino, guess, more/less and the /number pot game."""
from __future__ import annotations

import logging
import random
import secrets
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import constants
from app.db import actions, ledger, stats
from app.middlewares import RequireUser
from app.services import keyboards
from app.services.action_registry import action_handler
from app.utils.filters import Trigger, casino_trigger
from app.utils.money import coin_form, fmt, fmt_money, parse_amount, quantize
from app.utils.telegram import safe_edit
from app.utils.text import args_of, esc

logger = logging.getLogger(__name__)

router = Router(name="games")
registered = Router(name="games-registered")
registered.message.middleware(RequireUser())
registered.callback_query.middleware(RequireUser())
router.include_router(registered)

CASINO_USAGE = "🎰 Используйте казино так: <code>/casino &lt;ставка&gt; [множитель]</code>\n\nПодробнее: /help_casino"


def _win_roll(probability: float) -> bool:
    return secrets.randbelow(1_000_000) < int(probability * 1_000_000)


# ---- casino ----------------------------------------------------------------
@dataclass
class CasinoResult:
    win: bool
    payout: Decimal
    profit: Decimal
    jackpot: Decimal
    balance: Decimal


async def run_casino(pool, user_id: int, bet: Decimal, multi: Decimal) -> CasinoResult | None:
    """Play one round atomically. Returns None if funds are insufficient."""
    code = ledger.user_code(user_id)
    win = _win_roll(float(constants.RTP_CASINO / multi))
    payout = (bet * multi).quantize(Decimal("0.01"), rounding=ROUND_DOWN) if win else Decimal("0.00")
    profit = payout - bet
    jackpot_won = Decimal("0.00")
    try:
        async with pool.acquire() as con:
            async with con.transaction():
                bank = await ledger.balance(con, ledger.BANK)
                if win and bank < profit:
                    return None
                legs = {code: profit, ledger.BANK: -profit}
                if win and constants.COMMISSION_CASINO > 0:
                    fee = quantize(profit * constants.COMMISSION_CASINO / 100)
                    legs[code] -= fee
                    legs[ledger.JACKPOT] = fee
                await ledger.post(con, "casino_win" if win else "casino_loss", legs, initiator_id=user_id,
                                  meta={"bet": str(bet), "multi": str(multi)})
                pot = await ledger.balance(con, ledger.JACKPOT)
                if pot >= constants.JACKPOT_MIN and random.random() < constants.JACKPOT_CHANCE:
                    await ledger.post(con, "casino_jackpot", {ledger.JACKPOT: -pot, code: pot}, initiator_id=user_id)
                    jackpot_won = pot
                balance = await ledger.balance(con, code)
    except ledger.InsufficientFunds:
        return None
    logger.info("Casino user=%s bet=%s multi=%s win=%s", user_id, bet, multi, win)
    return CasinoResult(win, payout, profit, jackpot_won, balance)


def _casino_text(result: CasinoResult, bet: Decimal, multi: Decimal) -> str:
    if result.jackpot > 0:
        total = result.jackpot + result.payout
        return f"🎉 <b>JACKPOT</b>\n\nВы получили {fmt_money(total)}! (+{fmt(total - bet)})"
    if result.win:
        return f"✅ <b>Успех!</b>\n\nВы выиграли {fmt_money(result.payout)}! (+{fmt(result.profit)}, {fmt(multi)}x)"
    return f"❌ <b>Неудача!</b>\n\nВы получили 0 коинов! (-{fmt(bet)}, {fmt(multi)}x)"


@registered.message(Command("casino"))
@registered.message(casino_trigger())
async def cmd_casino(message: Message, pool, user) -> None:
    tokens = args_of(message)
    if len(tokens) not in (1, 2):
        await message.reply(CASINO_USAGE)
        return
    balance = quantize(user["balance"])
    bet = parse_amount(tokens[0], all_value=balance)
    multi = Decimal("2") if len(tokens) == 1 else parse_amount(tokens[1])
    if bet is None or multi is None:
        await message.reply("<b>Ставка и множитель должны быть числами!</b>")
        return
    if bet < constants.MIN_BET_CASINO:
        await message.reply(f"<b>Ставка не может быть меньше {fmt(constants.MIN_BET_CASINO)}.</b>")
        return
    if bet > constants.MAX_BET_CASINO:
        await message.reply(f"<b>Ставка не может быть больше {fmt(constants.MAX_BET_CASINO)}.</b>")
        return
    if multi < constants.MIN_MULTI_CASINO:
        await message.reply(f"<b>Множитель не может быть меньше {fmt(constants.MIN_MULTI_CASINO)}.</b>")
        return
    if multi > constants.MAX_MULTI_CASINO:
        await message.reply(f"<b>Множитель не может быть больше {fmt(constants.MAX_MULTI_CASINO)}.</b>")
        return
    if balance < bet:
        await message.reply("<b>У вас недостаточно средств.</b> Посмотреть баланс: /money")
        return
    async with pool.acquire() as con:
        bank = await ledger.balance(con, ledger.BANK)
        if bank < bet * multi - bet:
            await message.reply("<b>Банк не может выплатить вам выигрыш при такой ставке.</b>")
            return
        if bet >= balance / 2 and user["casino_warning"]:
            action_id = await actions.create(con, "casino", user["id"], {"bet": str(bet), "multi": str(multi)}, message.chat.id)
            await message.reply(
                f"{esc(user['name'])}, ваша ставка не меньше 50% вашего баланса! Вы уверены?",
                reply_markup=keyboards.confirm_kb(action_id, "ПОДТВЕРДИТЬ", "ОТМЕНИТЬ"),
            )
            return
    result = await run_casino(pool, user["id"], bet, multi)
    if result is None:
        await message.reply("❌ Недостаточно средств у вас или в банке.")
        return
    await message.reply(_casino_text(result, bet, multi))


@action_handler("casino")
async def confirm_casino(call: CallbackQuery, action, *, pool, **_) -> None:
    bet, multi = Decimal(action["payload"]["bet"]), Decimal(action["payload"]["multi"])
    result = await run_casino(pool, action["owner_id"], bet, multi)
    await safe_edit(call, "❌ Недостаточно средств у вас или в банке." if result is None else _casino_text(result, bet, multi))
    await call.answer()


@router.message(Command("help_casino"))
async def cmd_help_casino(message: Message, pool) -> None:
    async with pool.acquire() as con:
        jackpot = await ledger.balance(con, ledger.JACKPOT)
    await message.reply(
        "♣ <b>Подробности о казино</b>\n\nПри выигрыше вы получаете ставку × множитель, при проигрыше теряете ставку.\n\n"
        f"RTP: {fmt(constants.RTP_CASINO * 100)}%\nКомиссия при выигрыше: {fmt(constants.COMMISSION_CASINO)}%\n"
        f"Jackpot: {fmt(jackpot)} coins"
    )


# ---- guess -----------------------------------------------------------------
@registered.message(Command("guess"))
async def cmd_guess(message: Message, pool, user) -> None:
    tokens = args_of(message)
    if len(tokens) != 2 or not tokens[1].isdigit():
        await message.reply("❌ Ошибка!\n\nИспользование:\n/guess &lt;ставка&gt; &lt;число 1-10&gt;")
        return
    number = int(tokens[1])
    bid = parse_amount(tokens[0], all_value=user["balance"])
    if bid is None or not 1 <= number <= 10:
        await message.reply("❌ Ошибка!\n\nСтавка — число, угадываемое число — от 1 до 10.")
        return
    if bid < constants.MIN_BID:
        await message.reply(f"❌ Ставка должна быть не меньше {fmt(constants.MIN_BID)} коина!")
        return
    profit = quantize(bid * constants.GUESS_MULTI * (100 - constants.COMMISSION_GUESS) / 100)
    rolled = secrets.randbelow(10) + 1
    won = rolled == number
    code = ledger.user_code(user["id"])
    try:
        async with pool.acquire() as con:
            async with con.transaction():
                if won:
                    if await ledger.balance(con, ledger.BANK) < profit:
                        await message.reply("Банк не может выплатить выигрыш при такой ставке.")
                        return
                    await ledger.post(con, "guess_win", {ledger.BANK: -profit, code: profit}, initiator_id=user["id"])
                else:
                    await ledger.post(con, "guess_loss", {code: -bid, ledger.BANK: bid}, initiator_id=user["id"])
    except ledger.InsufficientFunds:
        await message.reply("❌ У вас недостаточно средств!")
        return
    if won:
        await message.reply(f"✅ <b>Успех!</b>\n\nВы выиграли {fmt_money(profit)}.\nЧисло: {rolled}")
    else:
        await message.reply(f"❌ <b>Неудача!</b>\n\nВы проиграли {fmt_money(bid)}.\nЧисло: {rolled}")


# ---- more / less -----------------------------------------------------------
@registered.message(Command("moreless"))
@registered.message(Trigger("бим", with_args=True))
async def cmd_moreless(message: Message, pool, user) -> None:
    tokens = args_of(message)
    usage = "Введите ставку после команды и угадайте, какое число будет следующим\n\n<code>/moreless &lt;ставка&gt;</code>"
    if len(tokens) != 1:
        await message.reply(usage)
        return
    bid = parse_amount(tokens[0], all_value=user["balance"])
    if bid is None:
        await message.reply(usage)
        return
    if bid < constants.MIN_BID:
        await message.reply(f"❌ Ставка должна быть не меньше {fmt(constants.MIN_BID)} коина!")
        return
    if bid > quantize(user["balance"]):
        await message.reply("❌ У вас недостаточно средств")
        return
    n = random.randint(80, 120)
    async with pool.acquire() as con:
        action_id = await actions.create(con, "moreless", user["id"], {"bid": str(bid), "n": n}, message.chat.id)
    await message.reply(
        f"💎 Ваша ставка: {fmt_money(bid)}\n\nВыпало число: <b>{n}</b>",
        reply_markup=keyboards.choice_kb(action_id, [("⬆️ БОЛЬШЕ", "up"), ("⬇️ МЕНЬШЕ", "down")]),
    )


@action_handler("moreless")
async def confirm_moreless(call: CallbackQuery, action, *, pool, choice: str, **_) -> None:
    uid = action["owner_id"]
    bid, n = Decimal(action["payload"]["bid"]), action["payload"]["n"]
    code = ledger.user_code(uid)
    won = _win_roll(constants.MORELESS_WIN_CHANCE)
    profit = quantize(bid * (100 - constants.COMMISSION_MORELESS) / 100)
    # The shown number is only a display: the next number is drawn so it matches the outcome.
    if (choice == "up") == won:
        next_n = random.randint(n + 1, 200)
    else:
        next_n = random.randint(1, n)
    try:
        async with pool.acquire() as con:
            async with con.transaction():
                if won:
                    if await ledger.balance(con, ledger.BANK) < profit:
                        await safe_edit(call, "Банк не может выплатить выигрыш при такой ставке.")
                        await call.answer()
                        return
                    await ledger.post(con, "moreless_win", {ledger.BANK: -profit, code: profit}, initiator_id=uid)
                else:
                    await ledger.post(con, "moreless_loss", {code: -bid, ledger.BANK: bid}, initiator_id=uid)
    except ledger.InsufficientFunds:
        await safe_edit(call, "❌ У вас недостаточно средств!")
        await call.answer()
        return
    if won:
        text = f"✅ <b>Успех!</b>\n\nВыпало число: <b>{next_n}</b> (было {n})\nВы выиграли {fmt_money(profit)}."
    else:
        text = f"❌ <b>Неудача!</b>\n\nВыпало число: <b>{next_n}</b> (было {n})\nВы проиграли {fmt_money(bid)}."
    await safe_edit(call, text)
    await call.answer()


# ---- number ----------------------------------------------------------------
@registered.message(Command("n", "number"))
async def cmd_number(message: Message, pool, user, runtime) -> None:
    tokens = args_of(message)
    async with pool.acquire() as con:
        pot = await ledger.balance(con, ledger.NUMBER_POT)
    hint = (f"Угадайте число от 1 до {constants.NUMBER_MAX} и получите {fmt_money(pot)}!\n"
            "<code>/number &lt;число&gt;</code>")
    if len(tokens) != 1:
        await message.reply(hint)
        return
    cooldown = float(pot) / 15 + constants.KD_NUMBER
    if tokens[0].lower() == "kd":
        await message.reply(f"⏳ Cooldown (KD): {cooldown:.2f} секунд.")
        return
    if not tokens[0].isdigit() or len(tokens[0]) > 6:
        await message.reply(hint)
        return
    left = runtime.cooldowns.hit(("number", user["id"]), cooldown)
    if left:
        await message.reply(f"⏳ Повторите через {left:.2f} сек.")
        return

    guess = int(tokens[0])
    async with pool.acquire() as con:
        async with con.transaction():
            target = await con.fetchval("SELECT (value)::int FROM kv WHERE key = 'number_target' FOR UPDATE")
            if guess != target:
                await message.reply("❌ Вы не угадали!")
                return
            pot = await ledger.balance(con, ledger.NUMBER_POT)
            if pot > 0:
                await ledger.post(con, "number_win", {ledger.NUMBER_POT: -pot, ledger.user_code(user["id"]): pot},
                                  initiator_id=user["id"])
            await stats.kv_set(con, "number_target", secrets.randbelow(constants.NUMBER_MAX) + 1)
    logger.info("User %s guessed the number, won %s", user["id"], pot)
    await message.reply(f"✅ Вы угадали число и получили {fmt_money(pot)}!")
