# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/ping.py

"""
Вычисляет пинг и отправляет пользователю с текущей датой
"""

import time
from datetime import datetime, timezone
from utils import log_handler

def setup(bot):
    @bot.message_handler(commands=['ping'])
    @log_handler
    def ping(msg):
        # Вычисление пинга
        st = time.time()
        bot.get_me()
        end_time = time.time()

        ping_to_server = (end_time - st) * 1000  # Пинг от сервера до телеграма

        bot.reply_to(msg, f"Ping: {int(ping_to_server)} ms\nUTC: {datetime.now(timezone.utc).replace(microsecond=0)}")
 
    return bot
