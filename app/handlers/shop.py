"""Shop: categories -> items -> purchase (paid into the bank)."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import ShopCb
from app.db import ledger, shop
from app.middlewares import RequireUser
from app.utils.money import fmt_money
from app.utils.telegram import safe_edit
from app.utils.text import esc

logger = logging.getLogger(__name__)

router = Router(name="shop")
router.message.middleware(RequireUser())
router.callback_query.middleware(RequireUser())


async def _categories_view(pool, owner: int):
    async with pool.acquire() as con:
        cats = await shop.categories(con)
    if not cats:
        return "🛒 <b>Магазин</b>\n\nМагазин пока пуст.", None
    kb = InlineKeyboardBuilder()
    for cat in cats:
        kb.button(text=cat["name"], callback_data=ShopCb(owner=owner, cat=cat["id"], item=0, buy=0))
    kb.adjust(2)
    return "🛒 <b>Магазин</b>\n\nВыберите категорию.", kb.as_markup()


@router.message(Command("shop"))
async def cmd_shop(message: Message, pool, user) -> None:
    text, markup = await _categories_view(pool, user["id"])
    await message.reply(text, reply_markup=markup)


@router.callback_query(ShopCb.filter())
async def on_shop(call: CallbackQuery, callback_data: ShopCb, pool) -> None:
    owner = callback_data.owner
    if call.from_user.id != owner:
        await call.answer("❌ Это не ваш магазин!", show_alert=True)
        return
    if callback_data.cat == 0:
        text, markup = await _categories_view(pool, owner)
        await safe_edit(call, text, markup)
        await call.answer()
        return
    if callback_data.item and callback_data.buy:
        try:
            async with pool.acquire() as con:
                bought = await shop.buy(con, owner, callback_data.item)
        except ledger.InsufficientFunds:
            await call.answer("❌ Недостаточно средств!", show_alert=True)
            return
        if bought is None:
            await call.answer("Товар не найден.", show_alert=True)
            return
        logger.info("User %s bought item %s", owner, bought["id"])
        await call.answer(f"✅ Куплено: {bought['name']}", show_alert=True)
        return
    async with pool.acquire() as con:
        cat = await shop.category(con, callback_data.cat)
        items = await shop.items(con, callback_data.cat) if cat else []
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=f"{item['name']} — {fmt_money(item['price'])}",
                  callback_data=ShopCb(owner=owner, cat=callback_data.cat, item=item["id"], buy=1))
    kb.button(text="⬅️ Назад", callback_data=ShopCb(owner=owner, cat=0, item=0, buy=0))
    kb.adjust(1)
    title = esc(cat["name"]) if cat else "?"
    await safe_edit(call, f"🛒 <b>{title}</b>\n\nНажмите на товар, чтобы купить его.", kb.as_markup())
    await call.answer()
