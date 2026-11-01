"""Shop catalogue and purchases."""
from __future__ import annotations

from decimal import Decimal

import asyncpg

from app.db import ledger


async def categories(con) -> list[asyncpg.Record]:
    return await con.fetch("SELECT id, name FROM shop_categories ORDER BY id")


async def category(con, category_id: int) -> asyncpg.Record | None:
    return await con.fetchrow("SELECT id, name FROM shop_categories WHERE id = $1", category_id)


async def items(con, category_id: int) -> list[asyncpg.Record]:
    return await con.fetch(
        "SELECT id, name, price FROM shop_items WHERE category_id = $1 ORDER BY id", category_id
    )


async def item(con, item_id: int) -> asyncpg.Record | None:
    return await con.fetchrow("SELECT id, name, price FROM shop_items WHERE id = $1", item_id)


async def add_item(con, category_name: str, name: str, price: Decimal) -> int:
    async with con.transaction():
        cat_id = await con.fetchval(
            "INSERT INTO shop_categories (name) VALUES ($1) "
            "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
            category_name,
        )
        return await con.fetchval(
            "INSERT INTO shop_items (category_id, name, price) VALUES ($1, $2, $3) "
            "ON CONFLICT (category_id, name) DO UPDATE SET price = EXCLUDED.price RETURNING id",
            cat_id, name, price,
        )


async def buy(con, user_id: int, item_id: int) -> asyncpg.Record | None:
    """Charge the user (price goes to the bank) and record the purchase."""
    async with con.transaction():
        found = await item(con, item_id)
        if not found:
            return None
        tx_id = await ledger.post(
            con,
            "shop_purchase",
            {ledger.user_code(user_id): -found["price"], ledger.BANK: found["price"]},
            initiator_id=user_id,
            meta={"item_id": item_id},
        )
        await con.execute(
            "INSERT INTO purchases (user_id, item_id, price, tx_id) VALUES ($1, $2, $3, $4)",
            user_id, item_id, found["price"], tx_id,
        )
        return found
