# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/credit.py

"""
Данный обработчик не используется из-за проблем с базой данных пользователей. В будущем он будет использоваться.
Пользователь безопасно выдает долг другому пользователю.
"""

from utils import log_handler

def setup(bot):
    @bot.message_handler(commands=['dolg'])
    @log_handler
    def dolg(msg):
        msg.reply_to(msg, "ты должен.")

        return

    return bot
