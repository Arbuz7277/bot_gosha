# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/test.py

"""
Это тестовый обработчик. Позже он будет удален.
"""

def setup(bot):
    @bot.message_handler(commands=['test'])
    def test(msg):
        msg.send_message(msg.chat.id, f"Привет, {msg.from_user.full_name}! Твой айди: {msg.from_user.id}")
        return

    return bot
