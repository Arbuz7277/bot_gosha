# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/__init__.py

import os
import time
from datetime import datetime, timedelta, timezone
import pytz
import json
import random
from config import*
import telebot
import emoji
import re
import numexpr
import uuid
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def save_users(data):
    with open(USERS_DATA, 'w', encoding='utf-8') as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )


def load_users():
    with open(USERS_DATA, 'r', encoding='utf-8') as f:
        return json.load(f)


def log_handler(func):
    """Декоратор для логирования вызова обработчиков"""
    logger.info(f"Loading handler {func.__name__}")
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        logger.info(f"Handler '{func.__name__}' called from {message.from_user.id}")
        return func(message, *args, **kwargs)
    
    return wrapper


class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[38;5;178m'
    RESET = '\033[0m'

def checker_borrow(bot):
    """Проверяет все долги и автоматически их списывает"""
    while True:
        try:
            users = load_users()
            
            with open(BORROW_DATA, 'r') as f:
                data = json.load(f)
            
            for i, request in enumerate(data):
                if time.time() - request['time'] > request['term'] and request['status'] == 'active':

                    sender = users[str(request['sender'])]
                    recipient = users[str(request['recipient'])]

                    sender['money'] -= request['amount']
                    recipient['money'] += request['amount']

                    request['status'] = "passed"


                    # Отправка уведомлений
                    try:
                        bot.send_message(request['sender'], f"Срок истек! Вы вернули пользователю @{recipient.get('username', 'Unknown')} {request['amount']} коинов.")
                        bot.send_message(request['recipient'], f"Срок истек! Вы получили от пользователя @{sender.get('username', 'Unknown')} {request['amount']} коинов.")
                    except Exception as e:
                        logger.warning(f"Failed to send notification: {type(e).__name__}: {e}")
          
            save_users(users)

            with open(BORROW_DATA, 'w') as f:
                json.dump(data, f, indent=4)

            time.sleep(30)
        except Exception as e:
            logger.error(f"Error in background thread: {type(e).__name__}: {e}")
            time.sleep(30)



if not os.path.exists(USERS_DATA):
    with open(USERS_DATA, 'w') as f:
        f.write('{}')
users = load_users()

roulette_bids = {}

if not os.path.exists(ROULETTE_DATA):
    with open(ROULETTE_DATA, 'w') as f:
        f.write('{}')
with open(ROULETTE_DATA, 'r', encoding='utf-8') as f:
    roulette_bids = json.load(f)

def create_transfer(sender, receiver, money, commission=0.0, type_transfer='TRANSFER'):
    with open(TRANSFER_DATA) as f:
        data = json.load(f)

    uuid_t = str(uuid.uuid4())
    data[uuid_t] = {}
    check = data[uuid_t]
    check['uuid'] = uuid_t
    check['create_at'] = str(datetime.now(timezone.utc))
    check['sender'] = int(sender)
    check['receiver'] = int(receiver)
    check['money'] = money
    check['commission'] = commission
    check['money_received'] = money - money * commission
    check['type'] = type_transfer

    with open(TRANSFER_DATA, 'w') as f:
        json.dump(data, f, indent=1)
    return uuid_t

def reduce_to_five(lst):
    """
    Оставляет в списке 5 элементов:
    - первый
    - последний
    - 3 равномерно распределённых между ними
    """
    if len(lst) <= 5:
        return lst
    
    indices = [0]  # первый индекс
    
    # Шаг для равномерного распределения
    step = (len(lst) - 1) / 4
    
    for i in range(1, 5):
        idx = int(round(i * step))
        indices.append(idx)
    
    indices = sorted(set(indices))
    
    return [lst[i] for i in indices]

def casino_load():
    with open('dp/casino.json', 'r') as f:
        return json.load(f)

def casino_save(data):
    with open('dp/casino.json', 'w') as f:
        json.dump(data, f, indent=4)

def casino_add(comm, win, user):
    data = casino_load()

    data['jackpot'] += comm

    if data['jackpot'] >= 200:
        if random.random() < 1 / 100:
            jackpot = data['jackpot']
            user['money'] += data['jackpot']
            data['paid'] += data['jackpot']
            data['total'] -= data['jackpot']
            data['jackpot'] = 0
            return True, jackpot, user

    if win < 0:
        data['paid'] += abs(win)
    else:
        data['received'] += abs(win)
    data['total'] += win
    casino_save(data)
    return False, data['jackpot'], user

def bot_stat(message, bot):
    with open('bot_stat.txt', 'r') as f:
        data = f.read()
        
    if data == 'off':
        bot.reply_to(message, '⚙ Извините, бот временно не работает по тех. причинам.')
        return True
    return False

def save_roulette(roulette_bids):
    with open(ROULETTE_DATA, 'w') as f:
        json.dump(roulette_bids, f, indent=4)

def usernam(user_id, bot):
    users = load_users()
    user_info = bot.get_chat(user_id)
    user = users.get(str(user_id))
    if not user:
        return
    users[str(user_id)]['username'] = user_info.username
    with open(USERS_DATA, 'w', encoding='utf-8') as f:
        json.dump(users,f,indent=4,ensure_ascii=False)

def load_other_data():
    with open(OTHER_DATA, 'r') as f:
        return json.load(f)

def save_other_data(other_data):
    with open(OTHER_DATA, 'w') as f:
        json.dump(other_data, f, indent=4)

def add_user(user_id, bot):
    users = load_users()
    """Добавляет пользователя"""
    if str(user_id) in users:
        return False

    user_info = bot.get_chat(user_id)

    other_data = load_other_data()
    last_id = other_data['last_id']

    name = emoji.replace_emoji(user_info.first_name, replace='')
    
    users[str(user_id)] = {}
    user = users[str(user_id)]

    user['name'] = user_info.first_name
    user['money'] = 0
    user['data_register'] = int(time.time())
    user['farm'] = time.time()
    user['admin'] = False
    user['username'] = user_info.username
    user['id'] = user_info.id
    user['gid'] = last_id + 1
    user['chat'] = []
    user['settings'] = {}

    settings = user['settings']
    settings['confid'] = {}
    settings['confid']['transfer_check'] = True
    settings['confid']['hide_username'] = True
    settings['confid']['hide_balance'] = False
    settings['confid']['hide_top'] = False

    other_data['last_id'] = last_id + 1

    with open(USERS_DATA, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4)
    save_other_data(other_data)
    
    return True

def add_chat(chat_id):
    """Добавляет чат айди"""
    file = FILE_CHATID

    if not os.path.exists(file):
        with open(file, 'w') as f:
            f.write('{"chat": []}')

    with open(file, 'r') as f:
        chat_ids = json.load(f)

    if int(chat_id) in chat_ids['chat']:
        return False

    chat_ids['chat'].append(chat_id)

    with open(file, 'w') as f:
        json.dump(chat_ids, f, indent=4)

    return True

def users_list():
    """Возвращает списoк пользователей"""
    with open(FILE_CHATID, 'r') as f:
        text = json.load(f)
        return text

def msg_all(text):
    """Отправляет сообщение всем пользователям"""
    list_user = users_list()

    er, on, bl = 0, 0, 0

    for user in list_user["chat"]:
        try:
            bot.send_message(user, text)
            on += 1
        except telebot.apihelper.ApiException as e:
            if  "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                bl += 1
        except:
            er += 1

    return [on, er, bl, list_user['chat']]

def admin_get(user_id):
    users = load_users()
    user = users.get(str(user_id))

    if user and user.get("admin", False):
        return True
    return False

def format_time_data(timestamp):
    msk_timezone = pytz.timezone('Europe/Moscow')
    
    dt_utc = datetime.utcfromtimestamp(int(timestamp))
    dt_utc = pytz.utc.localize(dt_utc)
    dt_msk = dt_utc.astimezone(msk_timezone)
    
    return dt_msk.strftime('%d/%m/%y')

def format_time_data_t(timestamp):
    msk_timezone = pytz.timezone('Europe/Moscow')
    
    dt_utc = datetime.utcfromtimestamp(int(timestamp))
    dt_utc = pytz.utc.localize(dt_utc)
    dt_msk = dt_utc.astimezone(msk_timezone)
    
    return dt_msk.strftime('%d/%m/%y  %H:%M:%S')


def top_add(user_id, chat):
    users = load_users()
    chat_id = int(chat)

    if chat_id > 0:
        return False
    
    if not users.get(str(user_id), False):
        return False
    
    if not users[str(user_id)].get('chat', False):
        users[str(user_id)]['chat'] = []
    
    if chat_id in users[str(user_id)]['chat']:
        return False
    
    users[str(user_id)]['chat'].append(chat_id)

    with open(USERS_DATA, 'w') as f:
        json.dump(users, f, indent=4)

def log(user_id, text):
    log_file = os.path.join('Logs', f'{user_id}.txt')
    
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f:
            pass
    with open(log_file, 'a') as f:
        f.write(f'[{format_time_data_t(time.time())}] {text}\n')

def get_premium(user_id):
    users = load_users()
    user = users.get(str(user_id), False)

    if not user:
        return False
    
    time_prem = user.get('premium', 0)

    if time.time() > time_prem:
        user['premium'] = 0
        return False
    
    return time_prem - time.time()

def bank_load():
    if not os.path.exists(BANK):
        with open(BANK, 'w') as f:
            f.write('{"money": 10000, "credits": {}}')
    with open(BANK, 'r') as f:
        return json.load(f)

def bank_save(databank):
    with open(BANK, 'w') as f:
        json.dump(databank, f, indent=4)

def bank_update(user_id, databank, users):
    if not str(user_id) in databank['credits']:
        return users
    
    if databank['credits'][str(user_id)][0] > time.time():
        return users

    users[str(user_id)]['money'] -= databank['credits'][str(user_id)][1] * 1.1
    databank['money'] += databank['credits'][str(user_id)][1] * 1.1
    del databank['credits'][str(user_id)]

    return users

def generate_unique_random(n1, n2, r):
    if r > (n2 - n1 + 1):
        return "It is impossible without repetitions."
    
    all_numbers = list(range(n1, n2 + 1))
    return random.sample(all_numbers, r)

def load_user_state(user_id):
    with open(USERS_STATES, 'r') as f:
        data = json.load(f)
    
    for uid, user_data in data.items():
        if str(uid) == str(user_id):
            return user_data
    
    return False

def menu(call, bot, types):
    user_id = call.from_user.id

    mar = types.InlineKeyboardMarkup()
    mar.add(types.InlineKeyboardButton('👤 Профиль', callback_data=f'profile:{user_id}'))
    mar.add(types.InlineKeyboardButton('🔗 Реферальный код', callback_data=f'referal:{user_id}'))
    mar.add(types.InlineKeyboardButton('⚙️ Настройки', callback_data=f'settings:{user_id}'))
    mar.add(types.InlineKeyboardButton('❓ Помощь', callback_data=f'help:{user_id}'))

    try:
        bot.edit_message_text(
            f'<b>Меню</b>\n\nВыбирайте раздел снизу.', 
            call.message.chat.id, 
            call.message.message_id,
            parse_mode='HTML', 
            reply_markup=mar
        )
    except:
        bot.send_message(
            call.message.chat.id,
            f'<b>Меню</b>\n\nВыбирайте раздел снизу.', 
            parse_mode='HTML', 
            reply_markup=mar
        )

def menu1(message, bot, types):
    user_id = message.from_user.id
    
    mar = types.InlineKeyboardMarkup()
    mar.add(types.InlineKeyboardButton('👤 Профиль', callback_data=f'profile:{user_id}'))
    mar.add(types.InlineKeyboardButton('🔗 Реферальный код', callback_data=f'referal:{user_id}'))
    mar.add(types.InlineKeyboardButton('⚙️ Настройки', callback_data=f'settings:{user_id}'))
    mar.add(types.InlineKeyboardButton('❓ Помощь', callback_data=f'help:{user_id}'))

    try:
        bot.edit_message_text(
            f'<b>Меню</b>\n\nВыбирайте раздел снизу.', 
            message.chat.id, 
            message.message_id,
            parse_mode='HTML', 
            reply_markup=mar
        )
    except:
        bot.send_message(
            message.chat.id,
            f'<b>Меню</b>\n\nВыбирайте раздел снизу.', 
            parse_mode='HTML', 
            reply_markup=mar
        )

def register(message, bot, types, users):
    if message.from_user.is_bot:
        return False

    if str(message.from_user.id) in users:
        return False

    if message.chat.type != 'private':
        markup = types.InlineKeyboardMarkup()
        starting_button = types.InlineKeyboardButton('Зарегестрироваться', url='t.me/gosha2200m_bot?start=0')
        markup.add(starting_button)
        bot.reply_to(message, 'Нажмите на кнопку для регистрации', reply_markup=markup)
        return True
        
    add_chat(message.chat.id)
    user_id = message.from_user.id
    result = add_user(user_id, bot)
    bank_update(user_id, databank, users)
    usernam(user_id, bot)

    if result == True:
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('👤 Меню', callback_data=f'menu:{user_id}')
        markup.add(btn1)
        bot.reply_to(message, "✅ Вы зарегестрированы!\n\nЕсли у вас есть код, введите его с помощью команды /code и получите 20 коинов!", reply_markup=markup)
    
    save_users(users)

def cregister(call, bot, types, users):
    if call.from_user.is_bot:
        return

    if call.message.chat.type != 'private':
        markup = types.InlineKeyboardMarkup()
        starting_button = types.InlineKeyboardButton('Зарегестрироваться', url='t.me/gosha2200m_bot?start=0')
        markup.add(starting_button)
        bot.edit_message_text('Нажмите на кнопку для регистрации', call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
        
    add_chat(call.message.chat.id)
    user_id = call.from_user.id
    result = add_user(user_id, bot)
    bank_update(user_id, databank, users)
    usernam(user_id, bot)

    if result == True:
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('👤 Меню', callback_data=f'menu:{user_id}')
        markup.add(btn1)
        bot.send_message(call.mesage.chat.id, "✅ Вы зарегестрированы!\n\nЕсли у вас есть код, введите его с помощью команды /code и получите 20 коинов!", reply_markup=markup)

def get_coin_form(number):
    num_str = str(number).lstrip('-')
    last_number = int(num_str[-1])

    if number % 1 == 0:
        if number == 1:
            return "коин"
        elif number in [2, 3, 4]:
            return "коина"
        elif number in [range(5, 20)]:
            return "коинов"
        else:
            if last_number == 1:
                return "коин"
            elif last_number in [2, 3, 4]:
                return "коина"
            else:
                return "коинов"
    else:
        if last_number == 1:
            return "коин"
        elif last_number in [2, 3, 4]:
            return "коина"
        else:
            return "коинов"

def mute_user(bot, chat_id, user_id, duration_minutes=30):
    until_date = datetime.now() + timedelta(minutes=duration_minutes)
    
    permissions = telebot.types.ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False
    )
    
    try:
        bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
            until_date=until_date
        )
        return True, ''
    except Exception as e:
        return False, e

def unmute_user(message, bot, chat_id, user_id):
    chat = bot.get_chat(chat_id)
    default_perms = chat.permissions
    
    try:
        bot.restrict_chat_member(chat_id, user_id, permissions=default_perms)
        return True, ''
    except Exception as e:
        return False, e

def gid_add(user_id):
    users = load_users()
    user = users[str(user_id)]
    if user.get('gid'):
        return
    
    last_id = load_other_data()['last_id']

    user['gid'] = last_id + 1

    other_data = load_other_data()
    other_data['last_id'] += 1

    save_other_data(other_data)
    save_users(users)

def format_time(text):
    try:
        time = int(text[:-1])
        format = text[-1]
    except:
        return 1
    
    if format == 'm':
        return time
    elif format == 'h':
        return time * 60
    elif format == 'd':
        return time * 24 * 60
    elif format == 'w':
        return time * 7 * 24 * 60
    else:
        return 1

def safe_calc(expression):
    expression = expression.strip()
    if not re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', expression):
        return "Prohibited symbols!"
    
    try:
        result = numexpr.evaluate(expression)
        return float(result)
    except:
        return "Invalid expression"



databank = bank_load()
