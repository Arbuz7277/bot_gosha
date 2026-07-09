# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# main.py

"""
Главный файл бота.
Он инициализирует бота, подключает обработчики и запускает поллинг.
"""

import os
import logging
import telebot
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO,
format="%(asctime)s : %(name)s %(levelname)s [%(filename)s:%(lineno)s] - %(message)s")

from handlers import setup_handlers

# Для улучшения читаемости логов
class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[38;5;178m'
    RESET = '\033[0m'

logger = logging.getLogger(__name__)

logger.info("Program is starting")

load_dotenv('secrets.env')
API_TOKEN = os.getenv('TOKEN')

def create_bot():
    """Создание и настройка экземпляра бота"""
    bot = telebot.TeleBot(API_TOKEN)
    bot = setup_handlers(bot)
    return bot

def main():
    """Запуск бота"""
    bot = create_bot()
    
    try:
        logger.info(f'{Color.GREEN}Bot running...{Color.RESET}')

        # Поллинг бота
        bot.infinity_polling(timeout=15, long_polling_timeout=5, allowed_updates=['message', 'callback_query', 'inline_query', 'my_chat_member'])
    except KeyboardInterrupt:
        logger.info("Program finished.")
    except Exception as e:
        logger.fatal(f'{Color.RED}{type(e).__name__}: {e}{Color.RESET}.')

if __name__ == "__main__":
    main()
