"""Time helpers (Moscow time is used for display)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.constants import TZ_NAME

TZ = ZoneInfo(TZ_NAME)
_DURATION = re.compile(r"(\d{1,6})([mhdw])")
_UNITS = {"m": 1, "h": 60, "d": 24 * 60, "w": 7 * 24 * 60}
MAX_MINUTES = 366 * 24 * 60


def parse_duration(text: str) -> int | None:
    """'30m' / '2h' / '3d' / '1w' -> minutes (None if invalid or out of range)."""
    match = _DURATION.fullmatch(text.strip().lower())
    if not match:
        return None
    minutes = int(match.group(1)) * _UNITS[match.group(2)]
    return minutes if 1 <= minutes <= MAX_MINUTES else None


def to_msk(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def fmt_date(dt: datetime) -> str:
    return to_msk(dt).strftime("%d/%m/%y")


def fmt_datetime(dt: datetime) -> str:
    return to_msk(dt).strftime("%d/%m/%y %H:%M:%S")


def now_msk() -> datetime:
    return datetime.now(TZ)


def human_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours} ч {minutes} мин и {secs} сек"
