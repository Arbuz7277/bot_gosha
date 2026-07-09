# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/mine_history.py

"""
Показывает последние блоки истории майнинга в виде JSON.
Доступно только для OWNER.
"""


import json
from utils import log_handler
from config import OWNER, MINE_HISTORY


def setup(bot):
    @bot.message_handler(commands=['mine_history'])
    @log_handler
    def mine_history(msg):
        if msg.from_user.id not in OWNER:
            return

        max_number_blocks = 10  # Максимальное количество блоков

        with open(MINE_HISTORY, 'r') as f:
            data = json.load(f)

        last_blocks = list(data.values())[-max_number_blocks:]  # Последние блоки
        text = json.dumps(last_blocks, indent=4)

        bot.send_message(msg.from_user.id, f"Последние {max_number_blocks} блоков\n\n```json\n{text}```", parse_mode="markdown")

    return bot
