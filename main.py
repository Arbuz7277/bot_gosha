# main.py

print("Loading base libaries...")
import os
import time
import random
import json
import socket
print("Loading logging...")
import logging
print("Loading telebot...")
import telebot
import threading
print("Loading datatime...")
from datetime import datetime, timedelta
print("Loading matplotlib...")
import matplotlib.pyplot as plt
import io
from dotenv import load_dotenv
print("Loading files...")
from handlers.commands import setup_handlers
from handlers.buttons import setup_buttons
from utils import *

class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[38;5;178m'
    RESET = '\033[0m'


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.system('clear')

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
    
    running_bot = True

    def exit():
        nonlocal running_bot
        logger.info(f'{Color.YELLOW}EXIT{Color.RESET}')
        running_bot = False

    try:
        err = False
        while True:
            if running_bot:
                try:
                    logger.info(f'{Color.GREEN}Bot running...{Color.RESET}')
                    if err:
                        for uid in OWNER:
                            bot.send_message(uid, f'Error: {err}')
                    bot.infinity_polling(timeout=15, long_polling_timeout=5, allowed_updates=['message', 'callback_query', 'inline_query', 'my_chat_member'])
                    time.sleep(5)
                except socket.gaierror as e:
                    logger.error(f'{Color.RED}Connection error. Error code: {e}{Color.RESET}')
                except ConnectionError as e:
                    logger.error(f'{Color.RED}Connection error. There in no Wi-Fi.{Color.RESET}')
                except KeyboardInterrupt:
                    exit()
                except Exception as e:
                    logger.error(f'{Color.RED}Error: {e}{Color.RESET}')
                    err = e
                    for uid in OWNER:
                        bot.send_message(uid, f'Error: {e}')
                    time.sleep(5)
                except:
                    logger.error(f'{Color.RED}UNKNOW ERROR{Color.RESET}')
            else:
                logger.info(f"{Color.YELLOW}Program stop due to admin.{Color.RESET}")
                break
    
    except KeyboardInterrupt:
        logger.info(f'{Color.YELLOW}EXIT{Color.RESET}')
        running_bot = False

if __name__ == "__main__":
    main()
