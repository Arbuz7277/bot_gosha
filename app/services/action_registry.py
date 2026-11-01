"""Registry of handlers for single-use confirmation buttons."""
from __future__ import annotations

from typing import Awaitable, Callable

ActionHandler = Callable[..., Awaitable[None]]
HANDLERS: dict[str, ActionHandler] = {}


def action_handler(kind: str) -> Callable[[ActionHandler], ActionHandler]:
    def decorator(func: ActionHandler) -> ActionHandler:
        if kind in HANDLERS:
            raise RuntimeError(f"duplicate action handler: {kind}")
        HANDLERS[kind] = func
        return func

    return decorator
