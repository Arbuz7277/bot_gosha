# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/balance.py

"""
Показывает текущий баланс
"""

import time
from utils import log_handler, load_users, add_chat, register, bot_stat, get_coin_form
from config import FARM_TIME
from telebot import types

def setup(bot):
    @bot.message_handler(commands=['money', 'balance', 'баланс', 'бал'])
    @log_handler
    def balance(message):
        users = load_users()
        if bot_stat(message, bot): return

        user_id = message.from_user.id
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return
        user = users[str(user_id)]

        # Проверка натсроек. Если баланс скрыт, то отправить в ЛС
        hide_balance = False
        if user.get('settings'):
            hide_balance = user['settings']['confid']['hide_balance']

        money = round(user.get('money', 0), 2)

        if hide_balance:
            bot.send_message(user_id, f"💰 Ваш баланс: {money:,.2f} {get_coin_form(money)}.")
            bot.reply_to(message, f'💰 Смотрите баланс в <a href="t.me/gosha2200m_bot">ЛС</a>', parse_mode='HTML', disable_web_page_preview=True)
            return

        text = f"💰 Ваш баланс: {money:,.2f} {get_coin_form(money)}.\n\n"

        # Если фарм активен, сообщить
        if time.time() - user['farm'] > FARM_TIME:
            text += "Введите /farm для фарма коинов!"

        bot.reply_to(message, text)

    return bot
