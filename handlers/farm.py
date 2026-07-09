# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/farm.py

"""
Фарминг для пользователей. Выдает случайное кол-во коинов раз в кулдаун.
Все коины он берет из банка и отказывается платить в случае недостатка коинов.
"""

import time
import secrets
import random
from utils import bot_stat, add_chat, register, bank_load, bank_save, load_user, save_users, log
from config import MAX_BALANCE_FARM, FARM_RANGE, MULTI_FARM

def setup(bot):
    @bot.message_handler(commands=['farm'])
    def cmd_farm(message):
        users = load_users()
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return

        user = users[str(user_id)]

        if user['money'] > MAX_BALANCE_FARM:
            bot.reply_to(message, '❌ Фармить возможно только если у вас баланс меньше 1000 коинов!')
            return
        
        hide_balance = False
        if user.get('settings'):
            hide_balance = user['settings']['confid']['hide_balance']

        databank = bank_load()
        bank_update(user_id, databank, users)
        if databank['money'] < 50:
            bot.reply_to(message, 'Недостаточно средств на балансе банка.')
            return

        usernam(user_id, bot)

        time_start = user.get('farm', 0)

        time1 = time.time() - time_start

        if time1 < FARM_TIME:
            bot.reply_to(message, f"❌ <b>Рано!</b>\n\n⏳ До фармы осталось {int(FARM_TIME - time1) // 3600} ч {int((FARM_TIME - time1) % 3600 // 60)} мин и {int((FARM_TIME - time1) % 60)} сек.", parse_mode='HTML')
            return

        user['farm'] = int(time.time())

        money = secrets.choice(range(*FARM_RANGE)) / 100

        p = random.random()

        if p < 0.01:
            money *= MULTI_FARM

        user['money'] = int((users[str(user_id)].get('money', 0) + money) * 100) / 100
        databank['money'] -= round(money, 2)

        save_users(users)
        bank_save(databank)
        log(user_id, f"Got {money} coins from /farm")

    return bot
