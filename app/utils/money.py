"""Money parsing and formatting."""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

from app.constants import ALL_WORDS

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("1000000000000")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def quantize(value: Decimal | int | float | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_amount(text: str, *, all_value: Decimal | None = None) -> Decimal | None:
    """Parse a user supplied amount.

    Accepts "12", "12.5", "12,5" and the words "all/все" (-> ``all_value``).
    Rejects signs, exponents, NaN/inf and absurdly large numbers.
    """
    raw = text.strip().lower().replace(",", ".")
    if raw in ALL_WORDS:
        return quantize(all_value) if all_value is not None else None
    if not _NUMBER.fullmatch(raw):
        return None
    value = Decimal(raw)
    if value > MAX_AMOUNT:
        return None
    return quantize(value)


def fmt(value: Decimal | int | float | str) -> str:
    """12.50 -> '12.5', 10.00 -> '10'."""
    text = f"{quantize(value):f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def coin_form(value: Decimal | int | float | str) -> str:
    """Russian plural for the word "coin"."""
    amount = quantize(value)
    if amount != amount.to_integral_value():
        return "коина"
    n = abs(int(amount))
    if 11 <= n % 100 <= 14:
        return "коинов"
    last = n % 10
    if last == 1:
        return "коин"
    if 2 <= last <= 4:
        return "коина"
    return "коинов"


def fmt_money(value: Decimal | int | float | str) -> str:
    return f"{fmt(value)} {coin_form(value)}"
