"""Process-wide mutable state."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.utils.throttle import Cooldowns


@dataclass
class Runtime:
    started_at: float = field(default_factory=time.time)
    maintenance: bool = False
    cooldowns: Cooldowns = field(default_factory=Cooldowns)
    busy_dice: set[int] = field(default_factory=set)
