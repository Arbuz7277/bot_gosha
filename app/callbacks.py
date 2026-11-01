"""Callback data factories."""
from aiogram.filters.callback_data import CallbackData


class ActionCb(CallbackData, prefix="act"):
    """Single-use confirmation stored in pending_actions."""
    id: str
    choice: str          # "n" = cancel, anything else = confirm / selected option


class MenuCb(CallbackData, prefix="menu"):
    action: str
    owner: int


class SettingCb(CallbackData, prefix="set"):
    owner: int
    key: str
    value: int


class RouletteCb(CallbackData, prefix="rl"):
    owner: int
    chat: int


class QuotePageCb(CallbackData, prefix="mq"):
    owner: int
    page: int


class QuoteCb(CallbackData, prefix="q"):
    qid: int
    act: str             # like | dislike | report


class ShopCb(CallbackData, prefix="shop"):
    owner: int
    cat: int
    item: int
    buy: int


class FeedbackCancelCb(CallbackData, prefix="fbc"):
    owner: int
