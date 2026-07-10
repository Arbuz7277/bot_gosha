# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/id.py

"""
Показывает контакты бота
"""

from utils import log_handler
from config import EMAIL, GITHUB

def setup(bot):
    @bot.message_handler(commands=['about'])
    @log_handler
    def about(msg):
        text = f"Email: {EMAIL}\n"
        text += f"GitHub: [repo]({GITHUB})\n\n"

        bot.reply_to(msg, text, parse_mode='markdown')

    return bot
