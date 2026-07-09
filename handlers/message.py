# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/message.py

"""
Возвращает JSON строку message.
"""

import json
from utils import log_handler

def setup(bot):
    @bot.message_handler(commands=['message', 'msg'])
    @log_handler
    def message(msg):
        msg_json_str = json.dumps(msg.json, indent=2)

        bot.reply_to(msg, f"```json\n{msg_json_str}```", parse_mode='markdown')

    return bot
