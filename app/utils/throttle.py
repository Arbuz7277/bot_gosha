"""In-memory cooldowns."""
from __future__ import annotations

import time
from typing import Hashable


class Cooldowns:
    """``hit(key, seconds)`` returns 0 and arms the cooldown, or the seconds left."""

    def __init__(self) -> None:
        self._until: dict[Hashable, float] = {}

    def hit(self, key: Hashable, seconds: float) -> float:
        now = time.monotonic()
        until = self._until.get(key, 0.0)
        if until > now:
            return until - now
        self._until[key] = now + seconds
        if len(self._until) > 10_000:
            self._until = {k: v for k, v in self._until.items() if v > now}
        return 0.0

    def left(self, key: Hashable) -> float:
        return max(0.0, self._until.get(key, 0.0) - time.monotonic())

    def arm(self, key: Hashable, seconds: float) -> None:
        self._until[key] = time.monotonic() + seconds
