# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/casino.py

"""
Казино с выбором множителя. Чем выше множитель, тем ниже шанс на выигрыш.
"""


import logging
import secrets
from telebot import types
from pathlib import Path
from config import MAX_BET_CASINO, MIN_BET_CASINO, MAX_MULTI_CASINO, MIN_MULTI_CASINO, RTP_CASINO, OWNER
from utils import bot_stat, add_chat, register, usernam, bank_load, bank_save, log_handler, load_users, log, save_users


logger = logging.getLogger(__name__)

def setup(bot):
    @bot.message_handler(func=lambda m: m.text and ('casino' in m.text.split()[0].lower() or 'деп' == m.text.split()[0].lower()) )
    @log_handler
    def casino(msg):
        # Инициализация пользователя
        if bot_stat(msg, bot): return

        add_chat(msg.chat.id)
        user = msg.from_user

        users = load_users()
        user_db = users[str(user.id)]
        if str(user.id) not in users:
            register(msg, bot, types, users)
            return
        usernam(user.id, bot)
        databank = bank_load()

        def add_money(user: dict, money: float) -> None:
            """Добавляет money пользователю и снимает их с банка"""
            # Проверка баланса банка
            if databank['money'] < money:
                raise ValueError("Not enough money in bank")

            # Добавление суммы
            user['money'] += money
            databank['money'] -= money
            bank_save(databank)
            save_users(users)

        # Проверка на количество аргументов
        args = msg.text.split()
        if len(args) not in (2, 3):
            bot.reply_to(msg, "�� Используйте казино по такой команде: `/casino <bet> <multi необязательно>`\n\nПодробнее: /casino_help", parse_mode='markdown')
            return

        # Создание аргументов
        try:
            # все - баланс пользователя
            if args[1].lower() == 'все':
                args[1] = round(user_db['money'], 2)

            bet = round(float(args[1]), 2)
            multi = 2 if len(args) != 3 else round(float(args[2]), 2)
        except ValueError:
            bot.reply_to(msg, "*bet и multi должны быть числами!*", parse_mode='markdown')
            return

        # настройки пользователя
        pass

        # Проверка значений аргументов
        # bet
        if bet < MIN_BET_CASINO:
            bot.reply_to(msg, f"*Ставка не может быть меньше {MIN_BET_CASINO}.*", parse_mode='markdown')
            return

        elif bet > MAX_BET_CASINO:
            bot.reply_to(msg, f"*Ставка не может быть больше {MAX_BET_CASINO}.*", parse_mode='markdown')
            return

        # multi
        if multi < MIN_MULTI_CASINO:
            bot.reply_to(msg, f"*Множитель не может быть меньше {MIN_MULTI_CASINO}.*", parse_mode='markdown')
            return

        elif multi > MAX_MULTI_CASINO:
            bot.reply_to(msg, f"*Множитель не может быть больше {MAX_MULTI_CASINO}.*", parse_mode='markdown')
            return

        # Проверка баланса пользователя
        if round(user_db['money'] ,2) < bet:
            bot.reply_to(msg, "*У вас недостаточно средств.* Посмотреть его можно с помощью команды /money", parse_mode='markdown')
            return

        # Проверка баланса банка
        if databank['money'] < bet * multi - bet:
            bot.reply_to(msg, "*Банк не может выплатить вам текущую ставку при выигрыше.*", parse_mode='markdown')
            return

        # --- Главная логика ---
        p = secrets.randbelow(1000) / 1000 < (RTP_CASINO / multi)  # Высчитывается шанс на выигрыш
        win = bet * multi  # Полная сумма выигрыша

        # Снимаем с баланса пользователя текущую ставку за игру
        add_money(user_db, -bet)

        if p:
            # Выигрыш
            add_money(user_db, win)
            log(user.id, f"Casino: [WIN] {bet} coins -> {win} ({multi}x) coins (+{win - bet})")
            bot.reply_to(msg, f"✅ *Успех!*\n\nВы выиграли {win:,.2f} коинов! (+{(win - bet):,.2f}, {multi}x)", parse_mode='markdown')
        else:
            # Проигрыш
            log(user.id, f"Casino: [LOSS] {bet} coins -> 0 ({multi}x) coins ({-bet})")
            bot.reply_to(msg, f"❌ *Неудача!*\n\nВы получили 0 коинов! ({-bet:,.2f}, {multi}x)", parse_mode='markdown')

        save_users(users)


    return bot
