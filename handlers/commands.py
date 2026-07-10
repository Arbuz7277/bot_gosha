# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Arbuz.
# handlers/commands.py

import telebot
import logging
logger = logging.getLogger(__name__)
from telebot import types
from config import*
from utils import*
import time
import pytz
from datetime import datetime, timedelta
from dotenv import load_dotenv
from queue import Queue
import matplotlib.pyplot as plt
import io
import secrets
import threading
import logging
import html
import ast
import re
import os
import uuid
import hashlib

class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[38;5;178m'
    RESET = '\033[0m'


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Chats update...")
if not os.path.exists('dp/chats.json'):
    with open('dp/chats.json', 'w') as f:
        f.write('{}')

with open('dp/chats.json', 'r') as f:
    chats_data = json.load(f)

for chat_id, chat_data in chats_data.items():
    dates = sorted(chat_data.keys())
    if not dates:
        continue

    now = datetime.now().strftime('%Y-%m-%d')
    if now not in dates:
        dates.append(now)

    st = datetime.strptime(min(dates), '%Y-%m-%d')
    et = datetime.strptime(max(dates), '%Y-%m-%d')

    while st <= et:
        date_str = st.strftime('%Y-%m-%d')

        if date_str not in chat_data:
            chat_data[date_str] = {}

        st += timedelta(days=1)

with open('dp/chats.json', 'w') as f:
    json.dump(chats_data, f, indent=2)



def setup(bot):
    @bot.message_handler(func=lambda message: message.forward_date is not None)
    def cmd_forward(message):
        return

    @bot.callback_query_handler(func=lambda call: True)
    def callback(call):
        owner_id = None
        data = call.data.split(":")
        action = data[0]

        if len(data) > 1:
            if data[1] != '0':
                owner_id = int(data[1])
        else:
            owner_id = None

        # === Проверка принадлежности ===
        if owner_id != None:
            if owner_id and call.from_user.id != owner_id:
                if len(data) != 1:
                    if data[1] != '0':
                        bot.answer_callback_query(call.id, "❌ Это не ваше действие!")
                        return

        if owner_id:
            if user_buttons.get(owner_id):
                if time.time() - user_buttons[owner_id] < 1.5:
                    bot.answer_callback_query(call.id, '⏳ Подождите немного...')
                    return
        user_buttons[owner_id] = time.time()

        chat_id = call.message.chat.id
        message_id = call.message.message_id

        # === Обработка действий ===
        if action == "pay":
            uuid = data[2]
            bot.send_message(call.from_user.id, f"UUID транзакции: <code>{uuid}</code>", parse_mode='HTML')

        elif action == "pay_accept":
            databank = bank_load()
            u1, u2, pay, user_id, reply_id, chat_id = users[str(data[1])], users[str(data[2])], round(float(data[3]), 2), data[1], data[2], int(data[4])
            
            if u1['money'] < pay:
                bot.edit_message_text('❌ У вас недостаточно средств!', call.message.chat.id, call.message.message_id)
                return
            bot.answer_callback_query(call.id, "✅ Перевод подтверждён!")
            hide_check1, hide_check2 = True, True
            hide_username1, hide_username2 = False, False

            if u1.get('settings'):
                hide_check1 = u1['settings']['confid']['transfer_check']
                hide_username1 = u1['settings']['confid']['hide_username']
            if u2.get('settings'):
                hide_check = u2['settings']['confid']['transfer_check']
                hide_username2 = u2['settings']['confid']['hide_username']

            # Перевод
            comm = round(pay / 100 * COMMISION_PAY, 2)
            pay_comm = round(pay - comm, 2)

            u1['money'] -= pay
            u2['money'] += pay_comm
            databank['money'] += comm
            date = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d/%m/%y__%H:%M:%S')

            log(user_id, f"Transfer: {pay_comm} coins to gosha_id_{u2['gid']} | commission {COMMISION_PAY}%")
            log(reply_id, f"Received: {pay_comm} from {user_id} | commission {COMMISION_PAY}%")

            save_users(users)
            uuid_transfer = str(create_transfer(data[1], data[2], pay, COMMISION_PAY/100))
            uuid_prefix = uuid_transfer[:8]

            mar = types.InlineKeyboardMarkup()
            mar.add(types.InlineKeyboardButton(text="Полный UUID", callback_data=f"pay:0:{uuid_transfer}", style="primary"))
            try:
                if hide_username1:
                    check1 = f"💰 <b>Перевод</b>\n\n<b>От кого:</b> <code>{u1['name']}</code>\n<b>Гоша айди:</b> <code>{u1.get('gid')}</code>\n<b>Сумма:</b> <code>{pay_comm}</code> {get_coin_form(pay_comm)}\n<b>Комиссия:</b> <code>{comm}</code> {get_coin_form(comm)}\n<b>Дата получения по МСК:</b> <code>{date}</code>\n<b>UUID:</b> <code>{uuid_prefix}</code>..."
                else:
                    check1 = f"💰 <b>Перевод</b>\n\n<b>От кого:</b> <code>{u1['name']}</code>\n<b>Юзернейм:</b> @{u1.get('username')}\n<b>Гоша айди:</b> <code>{u1.get('gid')}</code>\n<b>Сумма:</b> <code>{pay_comm}</code> {get_coin_form(pay_comm)}\n<b>Комиссия:</b> <code>{comm}</code> {get_coin_form(comm)}\n<b>Дата получения по МСК:</b> <code>{date}</code>\n<b>UUID:</b> <code>{uuid_prefix}</code>..."
                if hide_username2:
                    check2 = f"✅ <b>Успешный перевод</b>\n\n<b>Получатель:</b> <code>{u2['name']}</code>\n<b>Гоша айди:</b> <code>{u2.get('gid')}</code>\n<b>Переведено:</b> <code>{pay_comm}</code> {get_coin_form(pay_comm)}\n<b>Комиссия:</b> <code>{comm}</code> {get_coin_form(comm)}\n<b>Дата отправки по МСК:</b> <code>{date}</code>\n<b>UUID:</b> <code>{uuid_prefix}</code>..."
                else:
                    check2 = f"✅ <b>Успешный перевод</b>\n\n<b>Получатель:</b> <code>{u2['name']}</code>\n<b>Юзернейм:</b> @{u2.get('username')}\n<b>Гоша айди:</b> <code>{u2.get('gid')}</code>\n<b>Переведено:</b> <code>{pay_comm}</code> {get_coin_form(pay_comm)}\n<b>Комиссия:</b> <code>{comm}</code> {get_coin_form(comm)}\n<b>Дата отправки по МСК:</b> <code>{date}</code>\nUUID: {uuid_prefix}..."
            except Exception as e:
                bot.edit_message_text(f"\n\n\n❌ Ошибка при составлении чека.\n\n{type(e).__name__}: {e}", call.message.chat.id, call.message.message_id)
                return

            text = ''

            try:
                if hide_check1:
                    bot.send_message(user_id, check2, parse_mode='HTML', reply_markup=mar)
            except:
                text += "❌ Ошибка отправки чека вам.\n"

            try:
                if hide_check2:
                    bot.send_message(reply_id, check1, parse_mode='HTML', reply_markup=mar)
            except:
                text += "❌ Ошибка отправки чека получателю."
            
            # if 1 < 0:
            #     bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
            #     return


            bot.edit_message_text("✅ Перевод успешно выполнен!", call.message.chat.id, call.message.message_id)
            bank_save(databank)

        elif action == "pay_cancel":
            bot.answer_callback_query(call.id, "❌ Перевод отменён!")
            bot.edit_message_text("❌ Перевод отменён.", call.message.chat.id, call.message.message_id)

        elif action == "mq":
            mq_action = data[2]
            current_page = int(data[3])
            path_file = "dp/quotes.json"
            message = call.message

            with open(path_file, 'r') as f:
                data = json.load(f)

            user = call.from_user

            quotes_id = []
            for qid, quote in data.items():
                if qid.isdigit() and quote['id'] == user.id:
                    quotes_id.append(int(qid))

            if len(quotes_id) == 0:
                bot.reply_to(message, "❌ <b>Вы еще не создали никаких цитат :(</b>\nСоздайте свою первую цитату с помощью /q", parse_mode='HTML')
                return
            quotes_per_page = QUOTES_PER_PAGE
            total_page = (len(quotes_id) + quotes_per_page - 1) // quotes_per_page

            page_data = other_data.setdefault('mq', {})
            page = page_data.get(str(user.id), 1)
            lpage = page
            page += 1 if mq_action == "up" else -1
            page = min(total_page, max(1, page))
            if page == lpage:
                bot.answer_callback_query(call.id, "No")
                return
            page_data[str(user.id)] = page

            page_start = (page - 1) * quotes_per_page
            page_end = page_start + quotes_per_page

            mar = types.InlineKeyboardMarkup()
            btn1 = types.InlineKeyboardButton("<", callback_data=f"mq:{user.id}:down:{page}")
            btn2 = types.InlineKeyboardButton(">", callback_data=f"mq:{user.id}:up:{page}")
            mar.add(btn1, btn2)


            quotes = quotes_id[page_start:page_end]

            text = f"💬 <b>Ваши цитаты</b>\nСтраница: {page}/{total_page}"
            for quote_id in quotes:
                quote = data[str(quote_id)]

                quote_text = quote['text']
                quote_date = quote['date']

                text += f"\n\n№{quote_id} ¦ {quote_text[:20]}...\nДата: {quote_date}"

            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=mar)

        elif action == "help":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('Назад', callback_data=f'menu:{call.from_user.id}'))
            bot.edit_message_text(f'<a href="https://rentry.co/tg-gosha">Команды</a>', call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)

        elif action == 'profile':
            user_id = call.from_user.id
            add_chat(call.message.chat.id)
            bank_update(user_id, databank, users)

            if str(user_id) not in users:
                cregister(call, bot, types, users)
                return

            adm = 'Нет'

            try:
                id = call.message.reply_to_message.from_user.id

                adm = admin_get(user_id)

                if not adm:
                    id = user_id
            except:
                id = user_id

            if not str(id) in users:
                bot.reply_to(message, "❌ У вас нету аккаунта.")
                return
            
            user = users[str(id)]

            hide_balance = False
            if user.get('settings'):
                hide_balance = user['settings']['confid']['hide_balance']

            admin = admin_get(id)

            if admin: adm = 'Админ'
            else: adm = 'Пользователь'

            t = int(user['data_register'])

            time_reg = format_time_data(t)

            if hide_balance == True:
                bal = 'hidden'
            else:
                bal = round(user['money'], 2)

            gid = user.get('gid')
            if not hide_balance:
                text = f"📊 Профиль {users[str(id)]['name']}\n\nИмя: `{users[str(id)]['name']}`\nБаланс: `{bal}` {get_coin_form(bal)}\nДата регистрации(dd/mm/yy): `{time_reg}`\nРанг: {adm}\nАйди: `{gid}`"
            else:
                text = f"📊 Профиль {users[str(id)]['name']}\n\nИмя: `{users[str(id)]['name']}`\nБаланс: `{bal}`\nДата регистрации(dd/mm/yy): `{time_reg}`\nРанг: {adm}\nАйди: `{gid}`"

            mar = types.InlineKeyboardMarkup()
            mar.add(types.InlineKeyboardButton('Назад', callback_data=f'menu:{user_id}'))

            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='markdown', reply_markup=mar)

        elif action == 'menu':
            menu(call, bot, types)

        elif action == 'referal':
            user_id = call.from_user.id
            add_chat(call.message.chat.id)
            if str(user_id) not in users:
                cregister(call, bot, types, users)
                return

            if not os.path.exists(REFERAL_FILE):
                with open(REFERAL_FILE, 'w') as f:
                    json.dump({}, f)
            
            with open(REFERAL_FILE, 'r') as f:
                referal = json.load(f)
            
            if not str(user_id) in referal:
                running = True
                while running:
                    running = False
                    referal_code = random.randint(100000, 999999)
                    for uid, data in referal.items():
                        if referal_code == referal.get('code'):
                            running = True
                
                referal[str(user_id)] = {}
                referal[str(user_id)]['code'] = referal_code
                referal[str(user_id)]['activated'] = False
                referal[str(user_id)]['users'] = []
                log(user_id, f"Referral: received a referral code: {referal_code}")
            else:
                if not referal[str(user_id)].get('code'):
                    running = True
                    while running:
                        running = False
                        referal_code = random.randint(100000, 999999)
                        for uid, data in referal.items():
                            if referal_code == data['code']:
                                running = True
                    
                    referal[str(user_id)]['code'] = referal_code
                    log(user_id, f"Referral: received a referral code: {referal_code}")
                
                if not referal[str(user_id)].get('activated'):
                    referal[str(user_id)]['activated'] = False
                if not referal[str(user_id)].get('users'):
                    referal[str(user_id)]['users'] = []
            
            code = referal[str(user_id)]['code']
            users_referal = len(referal[str(user_id)]['users'])

            with open(REFERAL_FILE, 'w') as f:
                json.dump(referal, f, indent=4)
            
            mar = types.InlineKeyboardMarkup()
            mar.add(types.InlineKeyboardButton('Назад', callback_data=f'menu:{user_id}'))
            
            bot.edit_message_text(f'Ваш реферальный код: <code>{code}</code>\nКод был активирован: <code>{users_referal}</code> раз\n\nt.me/gosha2200m_bot?start={code}\nПриглашайте людей с помощью этой ссылки получайте по 20 коинов за человека', call.message.chat.id, call.message.message_id, parse_mode='HTML', disable_web_page_preview=True, reply_markup=mar)

        elif action == "quote":
            def create_mar(like, dislike, qid):
                mar = types.InlineKeyboardMarkup()
                btn_like = types.InlineKeyboardButton(f"{len(like)} 👍", callback_data=f"quote:0:{qid}:like")
                btn_dislike = types.InlineKeyboardButton(f"{len(dislike)} 👎", callback_data=f"quote:0:{qid}:dislike")
                btn_report = types.InlineKeyboardButton("⚠ Report", callback_data=f"quote:0:{qid}:report", style="danger")
                mar.add(btn_like, btn_dislike)
                mar.add(btn_report)

                return mar

            qid = data[2]
            do = data[3]
            user_id = call.from_user.id

            with open("dp/quotes.json", 'r') as f:
                qdata = json.load(f)

            quote = qdata[str(qid)]
            
            if do == "like":
                if user_id in quote['like']:
                    quote['like'].remove(user_id)
                elif user_id in quote['dislike']:
                    quote['dislike'].remove(user_id)
                    quote['like'].append(user_id)
                else:
                    quote['like'].append(user_id)
                mar = create_mar(quote['like'], quote['dislike'], qid)
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=mar)
            elif do == "dislike":
                if user_id in quote['dislike']:
                    quote['dislike'].remove(user_id)
                elif user_id in quote['like']:
                    quote['like'].remove(user_id)
                    quote['dislike'].append(user_id)
                else:
                    quote['dislike'].append(user_id)
                mar = create_mar(quote['like'], quote['dislike'], qid)
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=mar)
            elif do == "report":
                if quote['verified'] is True:
                    bot.answer_callback_query(call.id, text="Эта цитата была проверена администрацией бота")
                    return
                for uid, user in users.items():
                    if user.get('admin'):
                        bot.send_message(int(uid), f"⚠ На цитату №{qid} был отправлен репорт. Вам нужно проверить эту цитату.")

                quote['verified'] = False
                bot.answer_callback_query(call.id, text="✅ Жалоба подана")
                bot.delete_message(chat_id, message_id)

            with open("dp/quotes.json", 'w') as f:
                json.dump(qdata, f, indent=4)




        elif action == 'shop':
            with open(SHOP_ITEMS, 'r') as f:
                    shop_items = json.load(f)

            id = data[2]
            category_id = data[2]

            if category_id == '0':
                user_id = call.from_user.id
                u = users.get(str(user_id), False)

                # Регистрация
                if not u:
                    markup = types.InlineKeyboardMarkup()
                    starting_button = types.InlineKeyboardButton('Зарегестрироваться', url='t.me/gosha2200m_bot?start=0')
                    markup.add(starting_button)
                    bot.edit_message_text('Нажмите на кнопку для регистрации', call.message.chat.id, call.message.message_id, reply_markup=markup)
                    return
                
                markup = types.InlineKeyboardMarkup(row_width=3)
                for item_name, item_data in shop_items.items():
                    a1 = item_name.split(':')
                    name = a1[1]
                    id = a1[0]
                    btn = types.InlineKeyboardButton(name, callback_data=f'shop:{user_id}:{id}')
                    markup.add(btn)
                
                bot.edit_message_text('<b>Магазин</b>\n\nВыберите категорию.', call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup)
                return

            found_category = False
            for category_key in shop_items.keys():
                if category_key.split(':')[0] == data[2]:
                    found_category = category_key
                    break
            
            if found_category:
                markup = types.InlineKeyboardMarkup(row_width=3)
                for item_name, item_data in shop_items[found_category].items():
                    item_id = item_data[0]
                    price = item_data[1]
                    btn = types.InlineKeyboardButton(f'{item_name} | Цена: {item_data[1]}', callback_data=f'shop:{owner_id}:{item_id}')
                    markup.add(btn)

                btn = types.InlineKeyboardButton("Назад", callback_data=f'shop:{owner_id}:0')
                markup.add(btn)
                bot.edit_message_text(f"{found_category.split(':')[1]}\n\nНажмите на предмет чтобы купить его.", call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif action == 'delete_account':
            if data[2] == 'f':
                bot.edit_message_text("❌ Отменено!", call.message.chat.id, call.message.message_id)
            elif data[2] == 't':
                try:
                    del users[str(owner_id)]
                    save_users(users)
                    bot.edit_message_text('✅ Аккаунт удален!', call.message.chat.id, call.message.message_id)
                except:
                    pass

        elif action == 'dice':
            databank = bank_load()
            def delayed_message(chat_id, bid, u1, u2, user_id, rid, users):
                bot.delete_message(call.message.chat.id, call.message.message_id)
                chat_id = call.message.chat.id
                with open(DICE_PATH, 'r') as f:
                    dice_data = json.load(f)
                
                if rid in dice_data:
                    bot.send_message(chat_id, f'<a href="tg://user?id={call.from_user.id}">{u2['name']}</a>, вы уже играете!', parse_mode='HTML')
                    return
                elif user_id in dice_data:
                    bot.send_message(chat_id, f'<a href="tg://user?id={call.from_user.id}">{u2['name']}</a>, <a href="tg://user?id={user_id}">{u1['name']}</a> уже играет!', parse_mode='HTML')
                    return
                
                dice_data[rid] = {}
                dice_data[user_id] = {}

                with open(DICE_PATH, 'w') as f:
                    json.dump(dice_data, f, indent=4)
                

                bot.send_message(chat_id, f'<a href="tg://user?id={user_id}">{u1['name']}</a> бросает кубик...', parse_mode='HTML')
                dice_message1 = bot.send_dice(call.message.chat.id, emoji='🎲')
                dice1 = dice_message1.dice.value
                time.sleep(5)

                bot.send_message(chat_id, f'<a href="tg://user?id={rid}">{u2['name']}</a> бросает кубик...', parse_mode='HTML')
                dice_message2 = bot.send_dice(call.message.chat.id, emoji='🎲')
                dice2 = dice_message2.dice.value
                time.sleep(5)

                commission = round(bid / 100 * COMMISION_DICE, 2)
                win = round(bid - commission, 2)

                if dice1 > dice2:
                    result = True
                    t = f'<a href="tg://user?id={user_id}">{u1['name']}</a> выиграл(а) {win} {get_coin_form(win)}'
                    u1['money'] += win
                    u2['money'] -= bid
                    databank['money'] += commission

                    log(user_id, f'Dice: [WIN] Won {win} coins with gosha_id_{u2['gid']} | {COMMISION_DICE}% commission')
                    log(rid, f'Dice: [LOSS] Loss {bid} coins with gosha_id_{u1['gid']}.')

                elif dice1 == dice2:
                    result = None
                    t = 'Ничья!'

                else:
                    result = False
                    t = f'<a href="tg://user?id={rid}">{u2['name']}</a> выиграл(а) {win} {get_coin_form(win)}'
                    u2['money'] += win
                    u1['money'] -= bid
                    databank['money'] += commission

                    log(rid, f'Dice: [LOSS] Loss {bid} coins with gosha_id_{u2['gid']}.')
                    log(user_id, f'Dice: [WIN] Won {win} coins with gosha_id_{u1['gid']} | {COMMISION_DICE}% commission')

                text = f'<a href="tg://user?id={user_id}">{u1['name']}</a>: {dice1}\n<a href="tg://user?id={rid}">{u2['name']}</a>: {dice2}\n\n' + t

                bot.send_message(call.message.chat.id, text, parse_mode='HTML')

                del dice_data[user_id]
                del dice_data[rid]

                with open(DICE_PATH, 'w') as f:
                    json.dump(dice_data, f, indent=4)

                save_users(users)

            user_id = data[2]
            rid = data[1]
            u1 = users[data[2]]
            u2 = users[data[1]]
            bid = round(float(data[3]), 2)

            if u2['money'] < bid:
                text = f'<a href="tg://user?id={rid}">{u2['name']}</a>, у вас недостаточно средств!'
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='HTML')
                return

            elif u1['money'] < bid:
                text = f'<a href="tg://user?id={user_id}">{u1['name']}</a>, у вас недостаточно средств!'
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='HTML')
                return
            
            thread = threading.Thread(
                target=delayed_message,
                args=(call.message.chat.id, bid, u1, u2, user_id, rid, users)
            )
            thread.start()

            bank_save(databank)
        
        elif action == 'dice_cancel':
            if call.from_user.id == int(data[2]) or call.from_user.id == int(data[3]):
                bot.edit_message_text("❌ Отклонено!", call.message.chat.id, call.message.message_id)
                return
            bot.answer_callback_query(call.id, "❌ Это не ваше действие!")

        elif action == 'settings':
            user_id = call.from_user.id

            if not str(user_id) in users:
                register(message, bot, types, users)
                return
            
            user = users.get(str(user_id))
            settings = user.get('settings')
            if not settings:
                user['settings'] = {}
                settings = user['settings']
                settings['confid'] = {}
                settings['notifications'] = {}

                settings['confid']['transfer_check'] = True
                settings['confid']['hide_username'] = True
                settings['confid']['hide_balance'] = True
                settings['confid']['hide_top'] = True

                settings['notifications']['casino_warning'] = True
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton('🔒 Конфиденциальность', callback_data=f'confid:{user_id}'))
            markup.add(types.InlineKeyboardButton('🔔 Уведомления', callback_data=f'notifications:{user_id}'))
            markup.add(types.InlineKeyboardButton('Назад', callback_data=f'menu:{user_id}'))

            bot.edit_message_text(f'⚙ Настройки\n\nГлавное меню', call.message.chat.id, call.message.message_id, reply_markup=markup)
            save_users(users)

        elif action == 'confid':
            user_id = call.from_user.id

            user = users.get(str(user_id))
            if not user:
                cregister(call, bot, types, users)
                return
            
            settings = user.get('settings')
            if not settings:
                logger.error(f'{Color.RED}Unknown kay "settings" in callback.confid{Color.RESET}')
                return
            
            confid = settings['confid']

            if True:
                if confid['transfer_check'] == True:
                    transfer_check_text = 'Получать чек перевода | вкл.'
                    transfer_check_call = 'transfer_check_off'
                else:
                    transfer_check_text = 'Получать чек перевода | выкл.'
                    transfer_check_call = 'transfer_check_on'

                if confid['hide_username'] == True:
                    hide_username_text = 'Скрыть username | вкл.'
                    hide_username_call = 'hide_username_off'
                else:
                    hide_username_text = 'Скрыть username | выкл.'
                    hide_username_call = 'hide_username_on'
                
                if confid['hide_balance'] == True:
                    hide_balance_text = 'Скрыть баланс | вкл.'
                    hide_balance_call = 'hide_balance_off'
                else:
                    hide_balance_text = 'Скрыть баланс | выкл.'
                    hide_balance_call = 'hide_balance_on'
                
                if confid['hide_top'] == True:
                    hide_top_text = 'Скрыть в топе | вкл.'
                    hide_top_call = 'hide_top_off'
                else:
                    hide_top_text = 'Скрыть в топе | выкл.'
                    hide_top_call = 'hide_top_on'
            
            mar = types.InlineKeyboardMarkup()
            mar.add(types.InlineKeyboardButton(transfer_check_text, callback_data=f'{transfer_check_call}:{user_id}'))
            mar.add(types.InlineKeyboardButton(hide_username_text, callback_data=f'{hide_username_call}:{user_id}'))
            mar.add(types.InlineKeyboardButton(hide_balance_text, callback_data=f'{hide_balance_call}:{user_id}'))
            mar.add(types.InlineKeyboardButton(hide_top_text, callback_data=f'{hide_top_call}:{user_id}'))
            mar.add(types.InlineKeyboardButton('Назад', callback_data=f'settings:{user_id}'))

            bot.edit_message_text('🔒 Конфиденциальные настройки', call.message.chat.id, call.message.message_id, reply_markup=mar)

        elif action == 'notifications':
            user_id = call.from_user.id

            user = users.get(str(user_id))
            if not user:
                cregister(call, bot, types, users)
                return
            
            settings = user.get('settings')
            if not settings:
                logger.error(f'{Color.RED}Unknown kay "settings" in callback.confid{Color.RESET}')
                return
            
            if not settings.get('notifications'):
                settings['notifications'] = {}
                settings['notifications']['casino_warning'] = True
            
            notif = settings.get('notifications')

            if True:
                if notif['casino_warning'] == True:
                    casino_warning_text = 'Предупреждение в казино | вкл.'
                    casino_warning_call = 'casino_warning_off'
                else:
                    casino_warning_text = 'Предупреждение в казино | выкл.'
                    casino_warning_call = 'casino_warning_on'
            
            mar = types.InlineKeyboardMarkup()
            mar.add(types.InlineKeyboardButton(casino_warning_text, callback_data=f'{casino_warning_call}:{user_id}'))

            mar.add(types.InlineKeyboardButton('Назад', callback_data=f'settings:{user_id}'))

            bot.edit_message_text('🔔 Уведомления', chat_id, message_id, reply_markup=mar)


        elif action == 'roulette':
            if data[2] == 'cancel':
                if roulette_bids.get(data[3]):
                    if roulette_bids[data[3]].get(str(call.from_user.id)):
                        for bid in roulette_bids[data[3]][str(call.from_user.id)]:
                            users[str(call.from_user.id)]['money'] += bid[0]
                            log(call.from_user_id, f'Roulette: [CANCEL] Canceled the bid [{bid[1]}] {bid[0]} coins.')
                        del roulette_bids[data[3]][str(call.from_user.id)]

                bot.edit_message_text('❌ Ставки отменены!', call.message.chat.id, call.message.message_id)
                bot.answer_callback_query(call.id, '❌ Ставки отменены!')

            
            save_roulette(roulette_bids)

        elif action == 'moreless':
            user_id = call.from_user.id
            p = random.random() < MORELESS_RTP / 200

            if data[2] == 'cancel':
                bot.edit_message_text('❌ Отменено!', chat_id, message_id)
                bot.answer_callback_query(call.id, '❌ Отменено!')
                return
            
            win = round(float(data[3]) - (float(data[3]) / 100 * COMMISION_MORELESS), 2)
            
            if users[str(call.from_user.id)]['money'] < float(data[3]):
                bot.edit_message_text('❌ У вас недостаточно средст!', chat_id, message_id)
                bot.answer_callback_query(call.id, '❌ У вас недостаточно средст!')
                return
            
            elif data[2] == 'up':
                if p:
                    number = random.randint(int(data[4]) + 1, 200)
                    log(user_id, f'Moreless: [WIN] Bid: {data[3]}, UP | Numbers: {data[4]}:{number} (+{win})')
                    bot.edit_message_text(f'Ваше число: {data[4]}\nВторое число: {number}\n\n✅ Вы выиграли {win} {get_coin_form(float(data[3]))}!', chat_id, message_id)
                else:
                    number = random.randint(1, int(data[4]))
                    log(user_id, f'Moreless: [LOSS] Bid: {data[3]}, UP | Numbers: {data[4]}:{number} (-{data[3]})')
                    bot.edit_message_text(f'Ваше число: {data[4]}\nВторое число: {number}\n\n❌ Вы проиграли {float(data[3])} {get_coin_form(float(data[3]))}!', chat_id, message_id)
            elif data[2] == 'down':
                if p:
                    number = random.randint(1, int(data[4]))
                    log(user_id, f'Moreless: [WIN] Bid: {data[3]}, DOWN | Numbers: {data[4]}:{number} (+{win})')
                    bot.edit_message_text(f'Число: {data[4]}\nВыпало:{number}\n\n✅ Вы выиграли {win} {get_coin_form(float(data[3]))}!', chat_id, message_id)
                else:
                    number = random.randint(int(data[4]) + 1, 200)
                    log(user_id, f'Moreless: [LOSS] Bid: {data[3]}, DOWN | Numbers: {data[4]}:{number} (-{data[3]})')
                    bot.edit_message_text(f'Число: {data[4]}\nВыпало:{number}\n\n❌ Вы проиграли {float(data[3])} {get_coin_form(float(data[3]))}!', chat_id, message_id)
            

            if p:
                users[str(call.from_user.id)]['money'] += round(win)
                databank['money'] -= round(win)
            else:
                users[str(call.from_user.id)]['money'] -= float(data[3])
                databank['money'] += float(data[3])

        elif action == 'feedback':
            if data[2] == 'cancel':
                if other_time.get('feedback', {}).get(str(owner_id)):
                    del other_time['feedback'][str(owner_id)]
                
                bot.edit_message_text('❌ Отклонено!', chat_id, message_id)
                bot.answer_callback_query(call.id, '❌ Отклонено!')

        elif action == 'casino':
            databank = bank_load()
            user_id = int(data[1])

            if data[2] == 'cancel':
                bot.edit_message_text('Ставка отменена!', chat_id, message_id)
                bot.answer_callback_query(call.id, 'Ставка отменена!')
                return
            
            bid = float(data[2])
            multi_arg = float(data[3]) or 2


            
            a = random.random()

            if multi_arg:
                p_chance = round(0.95 / multi_arg, 5)

                if a <= p_chance:
                    p = 1
                else:
                    p = 0
            else:
                if a <= 0.525:
                    p = 0
                elif a > 0.475:
                    p = 1
                
            if bid * multi_arg - bid > databank['money']:
                bot.edit_message_text('❌ Недостаточно денег в банке.', chat_id, message_id)
                return
            
            if bid > users[str(user_id)].get('money', 0):
                bot.edit_message_text('❌ Ошибка!\n\nНедостаточно средств. Для просмотра баланса введите /money', chat_id, message_id)
                return

            if p == 1:
                if multi_arg:
                    multi = multi_arg
                else:
                    multi = 2
                win = round(bid * multi / 100 * (100 - CASINO_COMISSION), 2) # bid * multi - commission
                users[str(user_id)]['money'] += win
                databank['money'] -= win

                log(user_id, f"Casino: [WIN] {bid} coins -> {win} ({multi}x) coins (+{win - bid})")
                text = f"✅ <b>Успех!</b>\n\nВы выиграли {win} {get_coin_form(win)}! (+{round(win - bid, 2)}, {multi}x)"

                result, jackpot, users[str(user_id)] = casino_add(bid * multi - win, win, users[str(user_id)])
                if result:
                    text = f"🎉 <b>JACKPOT</b>\n\nВы получили {jackpot + win} {get_coin_form(jackpot + win)}! (+{round(jackpot + win - bid)})"
                bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML')

            elif p == 0:  # qwerty22
                multi = 0
                loser = round(bid * multi / 100 * (100 - CASINO_COMISSION), 2) # bid + multi - commission
                databank['money'] -= loser
                users[str(user_id)]['money'] += loser

                log(user_id, f"Casino: [LOSS] {bid} coins -> {loser} ({multi}x) coins ({bid - loser})")

                text = f"❌ <b>Неудача!</b>\n\nВы получили {loser} {get_coin_form(bid)}! ({round(loser - bid, 2)}, {multi}x)"

                result, jackpot, users[str(user_id)] = casino_add(0, loser, users[str(user_id)])
                if result:
                    text = f"🎉 <b>JACKPOT</b>\n\nВы получили {jackpot + loser} {get_coin_form(jackpot + loser)}! (+{round(jackpot + loser - bid)})"

                bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML')
                
            users[str(user_id)]['money'] -= bid
            save_users(users)
            databank['money'] += bid
            bank_save(databank)



        # === Settings ===
        else:
            # Confid
            if action == 'transfer_check_off':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['confid']['transfer_check'] = False
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'confid:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            
            elif action == 'transfer_check_on':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['confid']['transfer_check'] = True
                save_users(users)

                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'confid:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)

            elif action == 'hide_username_off':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['confid']['hide_username'] = False
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'confid:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            
            elif action == 'hide_username_on':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['confid']['hide_username'] = True
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'confid:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            
            elif action == 'hide_balance_off':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['confid']['hide_balance'] = False
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'confid:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            
            elif action == 'hide_balance_on':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['confid']['hide_balance'] = True
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'confid:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            
            elif action == 'hide_top_off':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['confid']['hide_top'] = False
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'confid:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            
            elif action == 'hide_top_on':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['confid']['hide_top'] = True
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'confid:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            
            # Notifications
            elif action == 'casino_warning_off':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['notifications']['casino_warning'] = False
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'notifications:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            
            elif action == 'casino_warning_on':
                user_id = call.from_user.id
                users[str(user_id)]['settings']['notifications']['casino_warning'] = True
                save_users(users)
                
                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('Назад', callback_data=f'notifications:{user_id}'))
                bot.edit_message_text('✅ Успешно! Настройки изменены', call.message.chat.id, call.message.message_id, reply_markup=mar)
            

    """Регистрация обработчиков команд"""
    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        if bot_stat(message, bot): return
        args = message.text.split()
        user_id = message.from_user.id
        
        if len(args) == 2:
            try:
                user_id = message.from_user.id
                add_chat(message.chat.id)
                if str(user_id) not in users:
                    register(message, bot, types, users)
                    return

                if len(args) != 2:
                    return
                
                if not os.path.exists(REFERAL_FILE):
                    return
                
                with open(REFERAL_FILE, 'r') as f:
                    referal = json.load(f)

                u_id = None

                for uid, data in referal.items():
                    if str(data.get('code', 0)) == args[1]:
                        u_id = uid
                        break

                if not u_id:
                    return

                if not referal.get(str(user_id)):
                    referal[str(user_id)] = {}
                    referal[str(user_id)]['activated'] = False
                
                if str(user_id) == u_id:
                    return

                if referal.get(str(user_id), {}).get('activated', True):
                    return
                
                if str(user_id) in referal[u_id]['users']:
                    return
                
                if u_id in referal.get(str(user_id), {}).get('users', []):
                    return
                
                referal[u_id]['users'].append(str(user_id))
                users[u_id]['money'] += 20
                users[str(user_id)]['money'] += 20
                referal[str(user_id)]['activated'] = True

                with open(REFERAL_FILE, 'w') as f:
                    json.dump(referal, f, indent=4)
                
                save_users(users)
                
                try:
                    bot.send_message(int(u_id), 'Пользователь активировал ваш код! Вам начислено 20 коинов.')
                except:
                    pass
                    
                bot.reply_to(message, '✅ Код активирован! Вам начислено 20 коинов.')
                log(user_id, f'Активировал реферальный код: {args[1]}')
            except Exception as e:
                bot.reply_to(message, f'❌ Произошла неизвестная ошибка с реферальным кодом.\n{e}')
        
        if not register(message, bot, types, users):
            menu1(message, bot, types)
        
    @bot.message_handler(commands=['mute'])
    def cmd_mute(message):
        if bot_stat(message, bot): return
        text = message.text
        try:
            chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
            
            # Проверяем, является ли пользователь администратором или создателем чата
            if chat_member.status in ['administrator', 'creator']:
                pass
            else:
                bot.reply_to(message, "Вы не администратор!")
                return
                
        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}")

        args = text.split(' ', 2)

        if len(args) < 2:
            bot.reply_to(message, "Недостаточно аргументов!")
            return

        try:
            chat_id = message.chat.id
            user_id = message.reply_to_message.from_user.id
            name = message.reply_to_message.from_user.first_name
            a = True
        except:
            bot.reply_to(message, f"Ответьте на сообщение!")
            return

        com = False
        if len(args) == 3:
            com = args[2]
        
        t = format_time(args[1])
        if t < 1:
            bot.reply_to(message, "Отрицательное время!")
            return
        
        try:
            member = bot.get_chat_member(chat_id, user_id)
            perms = member.can_send_messages
            
            # Если хотя бы одно ограничение стоит в False — пользователь в муте
            if perms is False:
                bot.reply_to(message, f"Пользователь в муте!")
                return
        except Exception as e:
            bot.reply_to(message, f"Ошибкая: \n\n{e}")

        mute, e = mute_user(bot, chat_id, user_id)
        if mute:
            text = f'Успешно!\n\nПользователь {name} замучен на {format_time(args[1])} минут!'
            if com:
                text += f'\n\nПричина: {com}'
            bot.reply_to(message, text)
        else:
            bot.reply_to(message, f"Произошла ошибка.\n\n{e}")

    @bot.message_handler(commands=['unmute'])
    def cmd_unmute(message):
        if bot_stat(message, bot): return
        text = message.text
        try:
            chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
            
            # Проверяем, является ли пользователь администратором или создателем чата
            if chat_member.status in ['administrator', 'creator']:
                pass
            else:
                # Пользователь не админ
                bot.reply_to(message, "Вы не администратор!")
                return
                
        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}")
        try:
            chat_id = message.chat.id
            user_id = message.reply_to_message.from_user.id
            name = message.reply_to_message.from_user.first_name
        except:
            bot.reply_to(message, f"Ответьте на сообщение!")
            return

        mute, e = unmute_user(message, bot, chat_id, user_id)
        if mute:
            bot.reply_to(message, f"Успешно!\n\nПользователь {name} размучен!")
        else:
            bot.reply_to(message, f"Произошла ошибка.\n\n{e}")

    @bot.message_handler(commands=['help'])
    def cmd_help(message):
        bot.reply_to(message, f'<a href="https://rentry.co/tg-gosha">Команды</a>', parse_mode='HTML', disable_web_page_preview=True)

    @bot.message_handler(commands=['menu'])
    def cmd_menu(message):
        if bot_stat(message, bot): return
        menu1(message, bot, types)

    @bot.message_handler(commands=['profile'])
    def cmd_profile(message):
        users = load_users()
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)

        if str(user_id) not in users:
            register(message, bot, types, users)
            return

        adm = 'Нет'

        try:
            id = message.reply_to_message.from_user.id

            adm = admin_get(user_id)

            if not adm:
                id = user_id
        except:
            id = user_id

        if not str(id) in users:
            bot.reply_to(message, "❌ У вас нету аккаунта.")
            return
        
        user = users[str(id)]

        hide_balance, hide_username = False, False
        if user.get('settings'):
            hide_balance = user['settings']['confid']['hide_balance']
            hide_username = user['settings']['confid']['hide_username']

        admin = admin_get(id)

        if admin: adm = 'Админ'
        else: adm = 'Пользователь'

        if user.get('data_register'):
            t = int(user['data_register'])
        else:
            t = int(time.time())

        time_reg = format_time_data(t)

        if hide_balance == True:
            bal = 'hidden'
        else:
            bal = round(user['money'], 2)

        gid = user.get('gid')
        text = f"📊 Профиль {users[str(id)]['name']}\n\nИмя: <code>{users[str(id)]['name']}</code>\nДата регистрации(dd/mm/yy): <code>{time_reg}</code>\nРанг: {adm}\nАйди: <code>{gid}</code>\n"
        if not hide_balance:
            text += f"Баланс: <code>{bal}</code> {get_coin_form(bal)}\n"
        if not hide_username:
            username = user.get("username")
            if not username:
                text += f"Юзернейм: <code>не указан</code>\n"
            text += f"Юзернейм: <code>@{username}</code>\n"

        try:
            bot.reply_to(message, text, parse_mode='HTML')
        except:
            bot.reply_to(message, text)

    @bot.message_handler(commands=['farm'])
    def cmd_farm(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return

        user = users[str(user_id)]

        if user['money'] > 1000:
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

        if p < 0.01:
            if hide_balance:
                bot.reply_to(message, f'✅ <b>Удача на вашей стороне!</b>\n\nВы нафармили {money:.2f} ({MULTI_FARM}x) {get_coin_form(money)}. Смотрите баланс с помощью команды /money', parse_mode='HTML')
            else:
                bot.reply_to(message, f'✅ <b>Удача на вашей стороне!</b>\n\nВы нафармили {money:.2f} ({MULTI_FARM}x) {get_coin_form(money)}.\nВаш баланс: {round(user['money'], 2)} {get_coin_form(round(user['money'], 2))}', parse_mode='HTML')
        else:
            if hide_balance:
                bot.reply_to(message, f'✅ <b>Успешно!</b>\n\nВы нафармили {money:.2f} {get_coin_form(money)}. Смотрите баланс с помощью команды /money', parse_mode='HTML')
            else:
                bot.reply_to(message, f'✅ <b>Успешно!</b>\n\nВы нафармили {money:.2f} {get_coin_form(money)}.\nВаш баланс: {round(user['money'], 2)} {get_coin_form(round(user['money'], 2))}', parse_mode='HTML')

    @bot.message_handler(commands=['pay'])
    def cmd_pay(msg):
        if bot_stat(msg, bot): return

        user = msg.from_user
        user_db = users[str(user.id)]

        add_chat(msg.chat.id)
        add_user(user.id, bot)
        usernam(user.id, bot)

        # Проверка количества аргументов
        args = msg.text.split(' ', 3)
        if len(args) < 2:
            bot.reply_to(msg, "❌ Неверные аргументы!\n\nПодробнее смотрите в /help")
            return
        
        base_comment = "No comment"

        # Проверка на ответ пользователя
        # --- Инийиализация аргументов ---
        if msg.reply_to_message:
            # Если да: /pay <amount> <comment>
            try:
                amount = round(float(args[1]), 2)
                username = msg.reply_to_message.from_user.username
                comment = args[2] if len(args) == 3 else base_comment
            except ValueError:
                bot.reply_to(msg, "*Сумма должна быть в виде числа.*", parse_mode='markdown')
                return
        else:
            # Иначе: /pay <username> <amount> <comment>
            try:
                username = args[1].replace('@', '', 1)
                if len(args) < 3:
                    bot.reply_to(msg, "*Укажите username или ответьте на сообщение для перевода.*", parse_mode='markdown')
                    return
                amount = round(float(args[2]), 2)
                comment = args[3] if len(args) == 4 else base_comment
            except ValueError:
                bot.reply_to(msg, "*Сумма должна быть в виде числа.*", parse_mode='markdown')
                return
              
        # --- Проверка значений аргументов ---
        # Минимальная сумма
        if amount < MIN_AMOUNT_PAY:
            bot.reply_to(msg, f"*Сумма переовода не может быть меньше {MIN_AMOUNT_PAY} коинов!*", parse_mode='markdown')
            return

        # Перевод самому себе
        if user.username == username:
            bot.reply_to(msg, "*Перевод самому себе невозможен.*", parse_mode='markdown')
            return

        # Проверка сущечтвования пользователя
        recipient_id = False
        for uid, data in users.items():
            if data.get('username') == username:
                recipient_id = uid
                break
        
        # Не найдено
        if not recipient_id:
            bot.reply_to(msg, f"*Пользователь {username} не найден.*", parse_mode='markdown')
            return

        # Проверка на наличие средств
        if user_db['money'] < amount:
            bot.reply_to(msg, "*У вас недостаточно средств.*", parse_mode='markdown')
            return

        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('ПОДТВЕРДИТЬ', callback_data=f'pay_accept:{user.id}:{recipient_id}:{amount}:{msg.chat.id}', style="success")
        btn2 = types.InlineKeyboardButton('ОТМЕНА', callback_data=f'pay_cancel:{user.id}', style="danger")
        markup.add(btn1)
        markup.add(btn2)
        bot.reply_to(msg, f"Подтвердите перевод на сумму `{amount}` коинов пользователю `{username}`.", parse_mode='markdown', reply_markup=markup)

    @bot.message_handler(commands=['show_transaction'])
    def cmd_show_transaction(msg):
        args = msg.text.split(' ', 1)
        if len(args) != 2:
            bot.reply_to(msg, 'введите после команды UUID транзакции')
            return

        with open("dp/transfers.json") as f:
            data = json.load(f)

        transaction = data.get(args[1])
        if not transaction:
            bot.reply_to(msg, "Транзакции не существует.")
            return

        transaction['sender'] = f"{str(transaction['sender'])[:4]}..."
        transaction['receiver'] = f"{str(transaction['receiver'])[:4]}..."
        json_text = json.dumps(transaction, indent=2)
        bot.reply_to(msg, f"Транзакция {args[1]}:\n\n```json\n{json_text}\n```", parse_mode='markdown')

    @bot.message_handler(commands=['my_transaction'])
    def cmd_my_transaction(msg):
        with open("dp/transfers.json", 'r') as f:
            data = json.load(f)
        
        income, outcome = [], []
        income_sum, outcome_sum = 0, 0
        for uuid, data in data.items():
            if data['sender'] == msg.from_user.id:
                outcome.append(uuid)
                outcome_sum += data['money']
            elif data['receiver'] == msg.from_user.id:
                income.append(uuid)
                income_sum += data['money_received']
        
        text = "Ваши транзакции\n\n"
        
        text += f"Общий доход: `{income_sum}`\n"
        text += f"Общий расход: `{outcome_sum}`\n"
        text += f"Общая прибыль: `{income_sum - outcome_sum}`\n\n"

        text += "Доход\n"
        for i, uuid in enumerate(income):
            text += f"{i}. `{uuid}`\n\n"

        text += "\nРасход\n"
        for i, uuid in enumerate(outcome):
            text += f"{i}. `{uuid}`\n\n"
        
        bot.send_message(msg.from_user.id, text, parse_mode='markdown')

    @bot.message_handler(commands=['exec'])
    def cmd_exec(msg):
        if msg.from_user.id not in OWNER: return
        code = msg.text.split('\n', 1)[1].strip()

        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            st = time.time()
            namespace = {}
            exec(code, namespace)
            output = sys.stdout.getvalue()
        except Exception as e:
            output = f"{type(e).__name__}: {e}"
        finally:
            sys.stdout = old_stdout
        total_time = time.time() - st

        bot.send_message(msg.chat.id, f"```output\n{output}```\n\nВремя выполнения: {total_time:.2f}s", parse_mode='markdown')

    @bot.message_handler(commands=['progress_time'])
    def progress_time(msg):
        def progressbar(current: int, total: int, length: int = 15, fill: str = '#', empty: str = '-') -> str:
            percent = current / total
            filled = int(length * percent)
            bar = fill * filled + empty * (length - filled)
            return f"[{bar}] {percent:.2%}"

        t = time.time()
        
        minute, hour, day = 60, 60*60, 60*60*24
        
        minute_bar = progressbar(t % minute, minute)
        hour_bar = progressbar(t % hour, hour)
        day_bar = progressbar(t % day, day)

        text =  f"Хз зачем я это сделал\nTime: {time.ctime(t)}\n\n```\n"
        text += f"min  {minute_bar}\n"
        text += f"hour {hour_bar}\n"
        text += f"day  {day_bar}\n```"

        bot.reply_to(msg, text, parse_mode='markdown')

    @bot.message_handler(commands=['nick'])
    def cmd_nick(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return

        args = message.text.split()

        if len(args) < 2:
            bot.reply_to(message, "❌ Ошибка!\n\nВведите ник после команды.\nИспользование:\n/nick nick123")
            return

        nick = message.text[6:]
        nick = nick.split('\n')

        if nick[0].strip() == '':
            bot.reply_to(message, "❌ Ник не может быть пустой!")
        
        nick[0] = emoji.replace_emoji(nick[0], replace='')

        if len(nick[0]) < 3 or len(nick[0]) > 32:
            bot.reply_to(message, "❌ Ошибка!\n\nНик должен быть длинной больше 3 и меньше 32 символов.")
            return

        users[str(user_id)]['name'] = nick[0].strip()

        save_users(users)
        log(user_id, f"Changed name to '{nick[0]}'")

        bot.reply_to(message, f"✅ Успешно!\n\nВы изменили свой ник на {nick[0]}.")

    @bot.message_handler(func=lambda m: m.text and ('casino' in m.text.split()[0].lower() or 'деп' == m.text.split()[0].lower()) )
    def cmd_casino(msg):
        users = load_users()
        # Инициализация пользователя
        if bot_stat(msg, bot): return

        add_chat(msg.chat.id)
        user = msg.from_user
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
            bot.reply_to(msg, f"✅ *Успех!*\n\nВы выиграли {win:.2f} коинов! (+{(win - bet):.2f}, {multi}x)", parse_mode='markdown')
        else:
            # Проигрыш
            log(user.id, f"Casino: [LOSS] {bet} coins -> 0 ({multi}x) coins ({-bet})")
            bot.reply_to(msg, f"❌ *Неудача!*\n\nВы получили 0 коинов! ({-bet:.2f}, {multi}x)", parse_mode='markdown')

        save_users(users)

    @bot.message_handler(commands=['help_casino'])
    def cmd_help_casino(message):
        data = casino_load()
        text = f"♣ Подробности о казино\n\nПри выигрыше вы получаете ставку, а при проигрыше проигрываете ставку.\n\nRTP: 95%\nКомиссия при выигрыше: {CASINO_COMISSION}%\nJackpot: {data['jackpot']:.2f} coins"

        bot.reply_to(message, text)

    @bot.message_handler(commands=['referral'])
    def cmd_referal(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return

        if not os.path.exists(REFERAL_FILE):
            with open(REFERAL_FILE, 'w') as f:
                json.dump({}, f)
        
        with open(REFERAL_FILE, 'r') as f:
            referal = json.load(f)
        
        if not str(user_id) in referal:
            running = True
            while running:
                running = False
                referal_code = random.randint(100000, 999999)
                for uid, data in referal.items():
                    if referal_code == data.get('code', 0):
                        running = True
            
            referal[str(user_id)] = {}
            referal[str(user_id)]['code'] = referal_code
            referal[str(user_id)]['activated'] = False
            referal[str(user_id)]['users'] = []
            log(user_id, f"Referral: received a referral code: {referal_code}")
        else:
            if not referal[str(user_id)].get('code'):
                running = True
                while running:
                    running = False
                    referal_code = random.randint(100000, 999999)
                    for uid, data in referal.items():
                        if referal_code == data.get('code'):
                            running = True
                
                referal[str(user_id)]['code'] = referal_code
                log(user_id, f"Referral: received a referral code: {referal_code}")
            
            if not referal[str(user_id)].get('activated'):
                referal[str(user_id)]['activated'] = False
            if not referal[str(user_id)].get('users'):
                referal[str(user_id)]['users'] = []
        
        code = referal[str(user_id)]['code']
        users_referal = len(referal[str(user_id)]['users'])

        with open(REFERAL_FILE, 'w') as f:
            json.dump(referal, f, indent=4)
        
        bot.reply_to(message, f'Ваш реферальный код: <code>{code}</code>\nКод был активирован: <code>{users_referal}</code> раз\n\nt.me/gosha2200m_bot?start={code}\nПриглашайте людей с помощью этой ссылки получайте по 20 коинов за человека', parse_mode='HTML', disable_web_page_preview=True)

    @bot.message_handler(commands=['code'])
    def cmd_code(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return

        args = message.text.split()

        if len(args) != 2:
            bot.reply_to(message, '❌ Ошибка!\n\nПример использования:\n/code 123456')
            return
        
        if not os.path.exists(REFERAL_FILE):
            bot.reply_to(message, '❌ Реферальная система не активирована')
            return
        
        with open(REFERAL_FILE, 'r') as f:
            referal = json.load(f)

        u_id = None

        for uid, data in referal.items():
            if data and 'code' in data and str(data['code']) == args[1]:
                u_id = uid
                break

        if not u_id:
            bot.reply_to(message, f'❌ Ошибка!\n\nКод {args[1]} не существует. Проверьте еще раз.')
            return
        
        if str(user_id) == u_id:
            bot.reply_to(message, '❌ Ошибка!\n\nЭто ваш код!')
            return

        if referal.get(str(user_id), {}).get('activated', False):
            bot.reply_to(message, '❌ Ошибка!\n\nВы уже активировали код!')
            return
        
        if str(user_id) in referal[u_id]['users']:
            bot.reply_to(message, '❌ Ошибка!\n\nВы уже активировали этот код!')
            return
        
        if u_id in referal.get(str(user_id), {}).get('users', []):
            bot.reply_to(message, '❌ Ошибка!\n\nЭтот пользователь уже активировал ваш код!')
            return
        
        if not referal.get(str(user_id)):
            referal[str(user_id)] = {}
            referal[str(user_id)]['activated'] = False
        
        referal[u_id]['users'].append(str(user_id))
        users[u_id]['money'] += 20
        users[str(user_id)]['money'] += 20
        referal[str(user_id)]['activated'] = True

        with open(REFERAL_FILE, 'w') as f:
            json.dump(referal, f, indent=4)
        
        save_users(users)
        
        try:
            bot.send_message(int(u_id), 'Пользователь активировал ваш код! Вам начислено 20 коинов.')
        except:
            pass
            
        bot.reply_to(message, '✅ Код активирован! Вам начислено 20 коинов.')
        log(user_id, f'Активировал реферальный код: {args[1]}')
        
    @bot.message_handler(commands=['top'])
    def cmd_top(message):
        if bot_stat(message, bot): return
        user_id = str(message.from_user.id)
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return
        bank_update(user_id, databank, users)

        if message.chat.id > 0:
            bot.reply_to(message, "❌ Эта команда работает только в группах!")
            return
        
        if time.time() - other_time.get('top', 0) < 2:
            return
        other_time['top'] = time.time()
        def get_active(uid):
            with open('dp/chats.json', 'r') as f:
                data = json.load(f)

            return data.get(str(message.chat.id), {}).get(datetime.now().strftime("%Y-%m-%d"), {}).get(str(uid), 0)

        top = 0
        chat_users = []
        for uid, user_data in users.items():
            if user_data and message.chat.id in user_data.get('chat', []):
                hide_balance = user_data.get('settings', {}).get('confid', {}).get('hide_balance', False)
                hide_top = user_data.get('settings', {}).get('confid', {}).get('hide_top', False)
                
                if hide_top:
                    continue
                    
                display_data = user_data.copy()
                if hide_balance:
                    display_data['money'] = 0
                    
                chat_users.append((uid, display_data))
        
        if len(chat_users) < 1:
            bot.reply_to(message, "💤 В чате пока нет пользователей с коинами.")
            return
        
        chat_users.sort(key=lambda x: x[1].get('money', 0), reverse=True)

        user_position = 0
        text = '<b>ТОП ЧАТА</b>\n\n'
        
        for i, (uid, user_data) in enumerate(chat_users[:15], 1):
            money = user_data.get('money', 0)
            name = html.escape(user_data.get('name', 'Unknow'))
            
            if user_id == uid:
                user_position = i
            
            # Эмодзи для мест
            medals = ["🥇", "🥈", "🥉"]
            medal = medals[i-1] if i <= 3 else f"{i}."
            
            # Выделение текущего пользователя
            if user_id == uid:
                name = f"✨{name}✨"
                top = i
            
            username = user_data.get('username')
            if not username:
                text += f'{medal} <a href="tg://openmessage?user_id={uid}">{name}</a> | {money:.2f} {get_coin_form(round(money, 2))} | {get_active(uid)} msg.\n'
            else:
                text += f'{medal} <a href=\"https://t.me/{username}">{name}</a> | {round(money, 2)} {get_coin_form(round(money, 2))} | {get_active(uid)} msg.\n'
        
        for i, (uid, user_data) in enumerate(chat_users, 1):
            if user_id == uid:
                top = i
        
        text += f"\n📊 <b>Вы на</b> <code>{top}</code> <b>месте.</b>"
        text += f"\n👥 <b>Всего в рейтинге:</b> <code>{len(chat_users)}</code>"

        with open('dp/chats.json') as f:
            data = json.load(f)

        chat_data = data[str(message.chat.id)]
        sorted_days = sorted(chat_data.keys(), key=lambda date: datetime.strptime(date, "%Y-%m-%d"))
        days_label = []
        today = datetime.now().strftime("%Y-%m-%d")
        for i, date in enumerate(sorted_days):
            if i % (len(sorted_days)//5) == 0 or date == today:
                days_label.append(date)
            else:
                days_label.append(' '*i)

        assets = []
        today_index = None
        for i, day in enumerate(sorted_days):
            day_total = sum(chat_data[day].values())
            assets.append(day_total)
            if day == today:
                today_index = i

        days = list(range(len(assets)))

        plt.figure(figsize=(10, 6))
        plt.bar(days_label, assets, width=0.9, alpha=0.8)
        plt.title("Chat active")
        plt.xlabel("Days")
        plt.ylabel("Messages")
        plt.grid(True, alpha=0.3)

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        text += f"\n\n💬 <b>Сообщений:</b> <code>{sum(chat_data.get(today, {}).values())}</code>"

        bot.send_photo(message.chat.id, buf, caption=text, parse_mode="HTML")

    @bot.message_handler(commands=['global_top'])
    def cmd_top(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        add_user(user_id, bot)
        databank = bank_load()
        bank_update(user_id, databank, users)

        text = 'Глобальный топ\n\n<blockquote expandable>'

        user = users.get(str(user_id), {})
            
        chat_users = []
            
        for uid, user_data in users.items():
            hide_balance = user_data.get('settings', {}).get('confid', {}).get('hide_balance', False)
            hide_top = user_data.get('settings', {}).get('confid', {}).get('hide_top', False)
                    
            if hide_top:
                continue
                    
            display_data = user_data.copy()
            if hide_balance:
                display_data['money'] = 0
                   
            chat_users.append((uid, display_data))

        chat_users.sort(key=lambda x: x[1].get('money', 0), reverse=True)
            
        for i, (uid, user_data) in enumerate(chat_users[:30], 1):
            money = user_data.get('money', 0)
            name = user_data.get('name', 'Unknown')
                
            text = text + f'{i}. {name} | {round(money, 2)} {get_coin_form(round(money, 2))}\n'
            
        top = None
        for i, (uid, user_data) in enumerate(chat_users, 1):
            if uid == str(user_id):
                top = i
                break
            
        if top is None:
            top = "не определено"
        
        bot.reply_to(message, text + f"</blockquote>\n\nВы на {top} месте из {len(chat_users)}.", parse_mode='HTML')

    @bot.message_handler(commands=['id_chat'])
    def id_chat(message):
        bot.reply_to(message, f"ID chat: {message.chat.id}")

    @bot.message_handler(commands=['random'])
    def cmd_random(message):
        args = message.text.split()

        if len(args) < 3:
            return
        
        try:
            n1 = int(args[1])
            n2 = int(args[2])
            if n1 > 1000 or n1 < -1000 or n2 > 1000 or n2 < -1000:
                return
            if len(args) == 4:
                r = int(args[3])
                if r > 100 or r < -100:
                    return
        except:
            bot.reply_to(message, 'Enter numbers!')
            return
        
        if len(args) == 4:
            number = generate_unique_random(n1, n2, r)
        else:
            number = random.randint(n1, n2)
        
        bot.reply_to(message, f"Number: {number}")
    
    @bot.message_handler(commands=['bank'])
    def cmd_bank(message):
        user_id = message.from_user.id
        add_chat(message.chat.id)
        databank = bank_load()

        bot.reply_to(message, f"Денег в банке: {databank['money']:.2f}")
    
    @bot.message_handler(commands=['my_credit'])
    def cmd_my_credit(message):
        return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return
        bank_update(user_id, databank, users)

        if not str(user_id) in databank['credits']:
            bot.reply_to(message, '❌ Ошибка! У вас нету кредита /bank')
            return
        
        money = databank['credits'][str(user_id)][1]
        tim = databank['credits'][str(user_id)][0] - time.time()
        text = f"Кредит {users[str(user_id)]['name']}:\n\nСумма кредита: {money:.2f}\nСумма задолженности: {(money * 1.1):.2f}\nОплата через: {int(tim // 3600)} часов и {int(tim % 3600 // 60)} минут."

        bot.reply_to(message, text)
    
    @bot.message_handler(commands=['credit'])
    def cmd_credit(message):
        bot.reply_to(message, "❌ <b>Кредит заблокирован!</b>", parse_mode='HTML')
        return

        user_id = message.from_user.id
        add_chat(message.chat.id)
        add_user(user_id, bot)
        bank_update(user_id, databank, users)

        args = message.text.split()

        if len(args) != 2:
            bot.reply_to(message, '❌ Ошибка! Введите число.\nПример: /credit 5.25')
            return
        
        try:
            number = float(args[1])
        except:
            bot.reply_to(message, '❌ Ошибка! Введите число.\nПример: /credit 5.25')
            return
        
        if number < 1:
            bot.reply_to(message, '❌ Введите сумму больше 1 коина!')
            return

        if str(user_id) in databank['credits']:
            bot.reply_to(message, '❌ У вас уже есть кредит!')
            return

        if databank['money'] * 0.01 < number:
            bot.reply_to(message, "❌ Ваша сумма больше максимального значения! /bank")
            return
        
        credit = [time.time() + 86400, number]
        databank['credits'][str(user_id)] = credit
        databank['money'] -= credit[1]
        users[str(user_id)]['money'] += credit[1]

        bank_save(databank)
        save_users(users)

        bot.reply_to(message, f'✅ Успешно! Вы взяли кредит на сумму {number:.2f} коинов.')
        log(user_id, f'Получил кредит на сумму {number} коинов.')
    
    @bot.message_handler(commands=['pay_credit'])
    def cmd_pay_credit(message):
        return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        add_user(user_id, bot)
        bank_update(user_id, databank, users)
        if not str(user_id) in databank['credits']:
            bot.reply_to(message, '❌ Ошибка! У вас нету кредита /bank')
            return
        
        if users[str(user_id)]['money'] < databank['credits'][str(user_id)][1] * 1.1:
            bot.reply_to(message, '❌ Ошибка! У вас недостаточно средств!')
            return
        
        users[str(user_id)]['money'] -= databank['credits'][str(user_id)][1] * 1.1
        databank['money'] += databank['credits'][str(user_id)][1] * 1.1
        del databank['credits'][str(user_id)]

        save_users(users)
        bank_save(databank)

        bot.reply_to(message, '✅ Оплачено!')
    
    @bot.message_handler(commands=['ball'])
    def ball(message):
        user_id = message.from_user.id
        add_chat(message.chat.id)
        text = message.text.replace('/ball', '').replace('/ball@gosha2200m_bot', '').strip()

        variant = random.choice(BALL_VARIABLES)

        bot.reply_to(message, f"{variant}{text}")

    @bot.message_handler(commands=['guess'])
    def cmd_guess(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return
        bank_update(user_id, databank, users)

        args = message.text.split()

        if len(args) != 3:
            bot.reply_to(message, "❌ Ошибка!\n\nИспользование:\n/guess <ставка> <число>")
            return
        
        try:
            number = int(args[2])

            if args[1].lower() == 'all':
                bid = users[str(user_id)]['money']
            else:
                bid = float(args[1])
            
            if number > 0 and number < 11:
                pass
            else:
                bot.reply_to(message, "❌ Ошибка!\n\nВведите число в диапазоне от 1 до 10.")
                return
        except:
            bot.reply_to(message, "❌ Вводите числа!")
            return
        
        money = users[str(user_id)]['money']
        
        if bid > money:
            bot.reply_to(message, "❌ У вас недотаточно средств!")
            return
        
        if bid < 0.1:
            bot.reply_to(message, '❌ Ставка должна быть больше 0.1 коина!')
            return
        
        number = int(number)
        a = random.randint(1, 10)

        win = bid * 8

        if a == number:
            users[str(user_id)]['money'] += win - win / 100 * 1
            databank['money'] -= win - win / 100 * 1
            log(user_id, f"Сыграл в угадай число. Результат: +{win}")
            bot.reply_to(message, f'✅ Успех!\n\nВы выиграли {win} коинов.\nЧисло: {a}')
        else:
            users[str(user_id)]['money'] -= bid
            databank['money'] += bid
            log(user_id, f"Сыграл в угадай число. Результат: -{bid}")
            bot.reply_to(message, f'❌ Неудача!\n\nВы проиграли {bid} коинов.\nЧисло: {a}')
        
        save_users(users)
        bank_save(databank)

    @bot.message_handler(commands=['ad'])
    def cmd_ad(message):
        if bot_stat(message, bot): return
        add_chat(message.chat.id)
        user_id = message.from_user.id
        args = message.text.split(' ', 2)

        if len(args) != 3:
            return

        text = message.text.replace('/ad', '').replace('/ad@gosha2200m_bot', '').replace(args[1], '', 1).strip()
        
        args = message.text.lower().split()

        if not args[1] in ['pin', 'not_pin']:
            return

        admin = admin_get(user_id)

        if not user_id in OWNER:
            return

        if text:
            bot.reply_to(message, 'Доставка сообщения...')
            list_user = users_list()

            er, on, bl = 0, 0, 0

            for user in list_user["chat"]:
                try:
                    sent_message = bot.send_message(user, text, parse_mode='HTML', disable_web_page_preview=True)
                    if args[1] == 'pin':
                        bot.pin_chat_message(user, sent_message.message_id)
                    on += 1
                except telebot.apihelper.ApiException as e:
                    if  "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                        bl += 1
                except:
                    er += 1

            bot.reply_to(message, f"✅ Закончено!\n\nДоставлено: {on}\nЗаблокировано:{bl}\nОшибка доставки: {er}")
            print(f'{Color.YELLOW}Command /ad completed.{Color.RESET}')
        else:
            bot.reply_to(message, "❌ Введите текст после команды!")
    
    @bot.message_handler(commands=['version'])
    def version(message):
        bot.reply_to(message, f"Version: {VERSION}")

    @bot.message_handler(commands=['add_admin'])
    def cmd_add_admin(message):
        if bot_stat(message, bot): return
        add_chat(message.chat.id)
        user_id = message.from_user.id

        if user_id not in OWNER:
            bot.reply_to(message, "❌ Вы не создатель!")
            return

        recipient = message.reply_to_message.from_user.id

        user = users.get(str(recipient), False)

        if user:
            name = users[str(recipient)].get('name', "Unknow")
            if users[str(recipient)].get('admin', False):
                bot.reply_to(message, f"❌ Ошибка!\n\n{name} уже админ.")
                return

            users[str(recipient)]['admin'] = True

            save_users(users)
            log(user_id, f"Выдал админку пользователю {recipient}")
            log(recipient, f"Получил админку от пользователя {user_id}")

            bot.reply_to(message, f"✅ Успешно!\n\n{name} получил админку.")

        else:
            bot.reply_to(message, "❌ Пользователь не зарегестрирован!\n\nДля регистрации введите /start")
            return

    @bot.message_handler(commands=['remove_admin'])
    def cmd_remove_admin(message):
        if bot_stat(message, bot): return
        add_chat(message.chat.id)
        user_id = message.from_user.id

        if user_id not in OWNER:
            bot.reply_to(message, "❌ Вы не создатель!")
            return

        recipient = message.reply_to_message.from_user.id

        if user_id == recipient:
            bot.reply_to(message, "❌ Ошибка! Выберите другого пользователя а не себя.")
            return

        user = users.get(str(recipient), False)

        if user:
            name = users[str(recipient)].get('name', "Unknow")
            if not users[str(recipient)].get('admin', False):
                bot.reply_to(message, f"❌ Ошибка!\n\n{name} и так не админ.")
                return

            users[str(recipient)]['admin'] = False

            save_users(users)
            log(user_id, f"Забрал админку пользователю {recipient}")
            log(recipient, f"Пользователь {user_id} удалил админку")

            bot.reply_to(message, f"✅ Успешно!\n\nАдминка у {name} удалена.")

        else:
            bot.reply_to(message, "❌ Пользователь не зарегестрирован!\n\nДля регистрации введите /start")
            return
    
    @bot.message_handler(commands=['set_money'])
    def adm_set_money(message):
        if bot_stat(message, bot): return
        add_chat(message.chat.id)
        user_id = message.from_user.id

        if user_id not in OWNER:
            return

        recipient = message.reply_to_message.from_user.id
        
        try:
            money = round(float(message.text.split()[1]), 2)
        except:
            bot.reply_to(message, "❌ Введите число!")
            return

        user = users.get(str(recipient), False)

        if user:
            name = user['name']
            user['money'] = money
            save_users(users)
        
        bot.reply_to(message, f"✅ Успешно!\n\nУ пользователя {name} теперь {money} {get_coin_form(money)}!")

    @bot.message_handler(commands=['all_money'])
    def all_money(message):
        if not users[str(message.from_user.id)]['admin']:
            return
        all_money = sum(user.get('money', 0) for user in users.values() if isinstance(user.get('money'), (int, float)))

        bot.reply_to(message, {round(all_money, 2)})

    @bot.message_handler(commands=['econ'])
    def cmd_econ(message):
        databank = bank_load()
        if message.from_user.id in OWNER:
            result = round(databank['money'] + sum(user.get('money', 0) for user in users.values() if isinstance(user.get('money'), (int, float))), 2)
            bot.reply_to(message, f'Всего: {result} {get_coin_form(result)}')

    @bot.message_handler(content_types=['new_chat_members'])
    def welcome(message):
        for new_member in message.new_chat_members:
            member_id = new_member.id
            
            if member_id == bot.get_me().id:
                bot.reply_to(message, "Я рад что вы меня добавили в чат 😊\nИспользуйте /help для просмотра моих команд")
                return

            user = users.get(str(member_id), False)
            if user:
                user['chat'].append(message.chat.id)
                bot.reply_to(message, f"Привет, <b>{new_member.first_name}</b>!", parse_mode='HTML')
        save_users(users)
    
    @bot.message_handler(content_types=['left_chat_member'])
    def handle_left_member(message):
        left_member = message.left_chat_member
        member_id = left_member.id
        
        user = users.get(str(member_id), False)
        if user and message.chat.id in user['chat']:
            user['chat'].remove(message.chat.id)
            bot.reply_to(message, f"Пока, <b>{left_member.first_name}</b> :(", parse_mode='HTML')
        save_users(users)

    @bot.message_handler(commands=['update'])
    def cmd_update(msg):
        if msg.from_user.id not in OWNER:
            return
        
        print("Chats update...")
        if not os.path.exists('dp/chats.json'):
            with open('dp/chats.json', 'w') as f:
                f.write('{}')

        with open('dp/chats.json', 'r') as f:
            chats_data = json.load(f)

        for chat_id, chat_data in chats_data.items():
            dates = sorted(chat_data.keys())
            if not dates:
                continue

            now = datetime.now().strftime('%Y-%m-%d')
            if now not in dates:
                dates.append(now)

            st = datetime.strptime(min(dates), '%Y-%m-%d')
            et = datetime.strptime(max(dates), '%Y-%m-%d')

            while st <= et:
                date_str = st.strftime('%Y-%m-%d')

                if date_str not in chat_data:
                    chat_data[date_str] = {}

                st += timedelta(days=1)

        with open('dp/chats.json', 'w') as f:
            json.dump(chats_data, f, indent=2)

        bot.reply_to(msg, "Update!")

    @bot.message_handler(commands=['graph'])
    def send_graph(message):
        try:
            if time.time() - other_time.get('graph', 0) < 10:
                return
            other_time['graph'] = time.time()

            # Читаем данные из файла
            coins = []
            with open('dp/history_money.txt', 'r') as f:
                coins = [float(line.strip()) for line in f if line.strip()]

            # Создаем часы для оси X
            hours = list(range(len(coins)))
            
            # Создаем график
            plt.figure(figsize=(10, 6))
            plt.plot(hours, coins, 'b-', linewidth=1)
            plt.title('Общий баланс пользователей по часам')
            plt.xlabel('Hours')
            plt.ylabel('Coins')
            plt.grid(True)
            
            # Сохраняем в память
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            
            # Отправляем
            bot.send_photo(message.chat.id, buf, 
                        caption=f"График баланса | Всего: {len(coins)} ч.")
            
            plt.close()
            
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {e}")

    @bot.message_handler(commands=['ugraph'])
    def ugraph(message):
        try:
            # Читаем данные из файла
            with open('dp/history_money_users.txt', 'r') as f:
                coins = [float(line.strip()) for line in f if line.strip()]
            
            # Создаем часы для оси X
            hours = list(range(len(coins)))
            
            # Создаем график
            plt.figure(figsize=(10, 6))
            plt.plot(hours, coins, 'b-', linewidth=2)
            plt.title('Средний баланс пользователя')
            plt.xlabel('Часы')
            plt.ylabel('Коины')
            plt.grid(True)
            
            # Сохраняем в память
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            
            # Отправляем
            bot.send_photo(message.chat.id, buf, 
                        caption=f"График баланса | Всего: {len(coins)} ч.")
            
            plt.close()
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {e}")

    @bot.message_handler(commands=['uptime'])
    def cmd_uptime(message):
        try:
            if not message.from_user.id in OWNER:
                return
            with open('/proc/uptime', 'r') as f:
                uptime_sec = float(f.readline().strip().split()[0])

            days = int(uptime_sec // 86400)
            hours = int((uptime_sec % 86400) // 3600)
            minutes = int((uptime_sec % 3600) // 60)
            seconds = int(uptime_sec % 60)

            text = f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}"

            bot.reply_to(message, text)
        except Exception as e:
            bot.reply_to(message, f"ERROR\n\n{type(e).__name__}: {e}")

    @bot.message_handler(commands=['info'])
    def cmd_info(message):
        if not message.from_user.id in OWNER:
            return

        st = time.time()
        bot.get_me()
        ping = int((time.time() - st) * 1000)

        utc = datetime.now().replace(microsecond=0)

        bank = bank_load()
        mbank = bank['money']

        all_money = sum(user.get('money', 0) for user in users.values())
        econ = mbank + all_money

        text = f"UTC: {utc}\nPing: {ping}ms\n\nBank: {mbank:.2f} coins ({int(mbank / econ * 100)}%)\nUsers money: {all_money:.2f} coins ({int(all_money / econ * 100)}%)\nEconomy: {econ:.2f} coins"

        bot.reply_to(message, text)
        

    @bot.message_handler(commands=['shop'])
    def shop(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        u = users.get(str(user_id), False)

        # Регистрация
        if not u:
            markup = types.InlineKeyboardMarkup()
            starting_button = types.InlineKeyboardButton('Зарегестрироваться', url='t.me/gosha2200m_bot?start=0')
            markup.add(starting_button)
            bot.reply_to(message, 'Нажмите на кнопку для регистрации', reply_markup=markup)
            return
        
        with open(SHOP_ITEMS, 'r') as f:
            shop_items = json.load(f)
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        for item_name, item_data in shop_items.items():
            a1 = item_name.split(':')
            name = a1[1]
            id = a1[0]
            btn = types.InlineKeyboardButton(name, callback_data=f'shop:{user_id}:{id}')
            markup.add(btn)
        
        bot.reply_to(message, '<b>Магазин</b>\n\nВыберите категорию.', parse_mode='HTML', reply_markup=markup)

    @bot.message_handler(commands=['users'])
    def cmd_users(message):
        num = len(users)
        bot.reply_to(message, f"Всего пользователей: {num}")

    @bot.message_handler(commands=['settings'])
    def cmd_settings(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id

        if not str(user_id) in users:
            register(message, bot, types, users)
            return
        
        user = users.get(str(user_id))
        settings = user.get('settings')
        if not settings:
            user['settings'] = {}
            settings = user['settings']
            settings['confid'] = {}
            settings['confid']['transfer_check'] = True
            settings['confid']['hide_username'] = False
            settings['confid']['hide_balance'] = False
            settings['confid']['hide_top'] = False
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton('🔒 Конфиденциальность', callback_data=f'confid:{user_id}'))

        bot.reply_to(message, f"Настройки\n\nВыберите раздел снизу", reply_markup=markup)
        save_users(users)
    
    @bot.message_handler(commands=['delete_account'])
    def cmd_delete_account(message):
        if bot_stat(message, bot): return
        user_id = str(message.from_user.id)

        if user_id not in users:
            register(message, bot, types, users)
        
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("ПОДТВЕРДИТЬ", callback_data=f"delete_account:{user_id}:t", style="success")
        btn2 = types.InlineKeyboardButton("ОТМЕНИТЬ", callback_data=f"delete_account:{user_id}:f", style="danger")
        markup.add(btn1)
        markup.add(btn2)
        bot.reply_to(message, "<b>Подтвердите удаление аккаунта.</b>\nПосле удаления все данные будут удалены!", parse_mode='HTML', reply_markup=markup)

    @bot.message_handler(commands=['dice'])
    def cmd_dice(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        args = message.text.lower().split()

        if str(user_id) not in users:
            register(message, bot, types, users)

        if len(args) not in [2, 3]:
            bot.reply_to(message, "❌ Неверные аргументы!\n\nИспользование:\n/dice <username> <bid> 1")
            return
        
        if len(args) == 2:
            try:
                bid = round(float(args[1]), 2)
            except:
                bot.reply_to(message, "❌ Неверные аргументы!\n\nИспользование:\n/dice <username> <bid> 2")
                return
            
            r_message = message.reply_to_message
            rid = None
            if r_message:
                rid = r_message.from_user.id
            else:
                bot.reply_to(message, "❌ Неверные аргументы!\n\nИспользование:\n/dice <username> <bid> 3")
                return
        

        elif len(args) == 3:
            try:
                bid = round(float(args[2]), 2)
            except:
                bot.reply_to(message, "❌ Неверные аргументы!\n\nИспользование:\n/dice <username> <bid> 2")
                return

            rid = None

            if args[1].isdigit():
                for uid, data in users.items():
                    if int(args[1]) == int(uid):
                        rid = int(uid)
                    elif int(args[1]) == data.get('gid'):
                        rid = int(uid)

            else:
                for uid, data in users.items():
                    un = data.get('username')
                    username = args[1].replace('@', '', 1).lower()
                    if un:
                        if username == un.lower():
                            rid = int(uid)

        if user_id == rid:
            bot.reply_to(message, '❌ Нельзя играть с самим собой!')
            return
        
        u1 = users.get(str(user_id))
        u2 = users.get(str(rid))

        if not u1 or not u2:
            bot.reply_to(message, f'❌ Игрок не зарегестрирован! {rid}')
            return

        if bid <= 0:
            bot.reply_to(message, "❌ Введите положительную ставку!")
            return

        if bid > u1['money']:
            bot.reply_to(message, '❌ У вас недостаточно средств!')
            return
        elif bid > u2['money']:
            bot.reply_to(message, '❌ У игрока недостаточно средств')
            return

        mar = types.InlineKeyboardMarkup()
        mar.add(types.InlineKeyboardButton('ПРИНЯТЬ', callback_data=f'dice:{rid}:{user_id}:{bid}', style="success"))
        mar.add(types.InlineKeyboardButton('ОТКЛОНИТЬ', callback_data=f'dice_cancel:0:{user_id}:{rid}', style="danger"))
        if set(u1['chat']) & set(u2['chat']):
            if bid % 1 != 0:
                bot.send_message(message.chat.id, f'<a href="tg://user?id={rid}">{u2['name']}</a>, <a href="tg://user?id={user_id}">{u1['name']}</a> хочет сыграть с вами в кости на {bid} {get_coin_form(bid)}.', parse_mode='HTML', reply_markup=mar)
            else:
                bot.send_message(message.chat.id, f'<a href="tg://user?id={rid}">{u2['name']}</a>, <a href="tg://user?id={user_id}">{u1['name']}</a> хочет сыграть с вами в кости на {int(bid)} {get_coin_form(int(bid))}.', parse_mode='HTML', reply_markup=mar)
        else:
            if bid % 1 != 0:
                bot.send_message(message.chat.id, f'{u2['name']}, {u1['name']} хочет сыграть с вами в кости на {bid} {get_coin_form(bid)}.', parse_mode='HTML', reply_markup=mar)
            else:
                bot.send_message(message.chat.id, f'{u2['name']}, {u1['name']} хочет сыграть с вами в кости на {int(bid)} {get_coin_form(int(bid))}.', parse_mode='HTML', reply_markup=mar)
        
    @bot.message_handler(commands=['time'])
    def cmd_time(message):
        t = format_time_data_t(int(time.time()))
        bot.reply_to(message, f'Точное время по МСК: <code>{t}</code>', parse_mode='HTML')

    @bot.message_handler(commands=['search_id'])
    def cmd_search_id(message):
        args = message.text.lower().split()
        if len(args) != 2:
            return
        bot.reply_to(message, f'URL: <a href="tg://user?id={args[1]}">{args[1]}</a>', parse_mode='HTML')

    @bot.message_handler(commands=['say'])
    def cmd_say(message):
        user_id = message.from_user.id
        if not user_id in OWNER:
            return
        
        print(f'INFO:handlers.commands:Message_from_owner: {Color.YELLOW}{message.text[5:]}{Color.RESET}')

    @bot.message_handler(commands=['send'])
    def cmd_send(message):
        args = message.text.split(' ', 2)
        if not message.from_user.id in OWNER:
            return
        
        if len(args) != 3:
            return
        
        bot.send_message(int(args[1]), args[2])

    @bot.message_handler(commands=['roulette'])
    def cmd_roulette(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        args = message.text.lower().split()
        if str(user_id) not in users:
            register(message, bot, types, users)
            return

        user = users[str(user_id)]

        if len(args) != 3:
            bot.reply_to(message, 'Играйте в рулетку! Аргументы:\n\n`/roulette <black/red/green or number> <bid>`', parse_mode='markdown')
            return
        
        bet_type = args[1]

        if bet_type.isdigit():
            multi = 36
            if 0 <= int(bet_type) <= 36:
                bet_type = int(bet_type)
            else:
                bot.reply_to(message, '❌ Пожалуйста, введите число от 0 до 36 или цвет!')
                return
        else:
            multi = 2
            if bet_type in ['black', 'черный', 'черная', 'черное', 'чёрное', 'чёрный', 'чёрная', 'ч', 'b']:
                bet_type = 'black'
            elif bet_type in ['red', 'красный', 'красная', 'красное', 'к', 'r']:
                bet_type = 'red'
            elif bet_type in ['green', 'зеленый', 'зеленая', 'зеленое', 'зелёный', 'зелёная', 'зелёное', 'з', 'g']:
                bet_type = 'green'
                multi = 36
            else:
                bot.reply_to(message, '❌ Пожалуйста, введите число от 0 до 36 или цвет!')
                return
        
        if args[2].lower() in ['all', 'все', 'вся', 'весь']:
            bid = round(user['money'], 2)
        elif args[2].replace('.', '', 1).isdigit():
            bid = round(float(args[2]), 2)
        else:
            bot.reply_to(message, 'Играйте в рулетку! Аргументы:\n\n`/roulette <black/red/green or number> <bid>`', parse_mode='markdown')
            return
        
        if bid > round(user['money'], 2):
            bot.reply_to(message, '❌ У вас недостаточно средств!')
            return
        
        elif bid < 0.1:
            bot.reply_to(message, '❌ Пожалуйста, введите ставку больше 0.1 коина!')
            return
        
        else:
            if not roulette_bids.get(str(message.chat.id)):
                roulette_bids[str(message.chat.id)] = {}
            if not roulette_bids[str(message.chat.id)].get(str(user_id)):
                roulette_bids[str(message.chat.id)][str(user_id)] = []
            roulette_bids[str(message.chat.id)][str(user_id)].append([bid, bet_type, multi])
            log(user_id, f'Roulette: [BID] Create bid [{bet_type}] {bid} coins.')
        
        user['money'] -= bid

        mar = types.InlineKeyboardMarkup()
        mar.add(types.InlineKeyboardButton('❌ ОТМЕНИТЬ СТАВКУ', callback_data=f'roulette:{user_id}:cancel:{message.chat.id}'))
        
        bot.reply_to(message, f'🎯 Вы создали ставку {bid} {get_coin_form(bid)} на {str(bet_type).upper()}\n\n🎰 Введите /spin чтобы покрутить рулетку.', reply_markup=mar)

        if not time_roulette.get(str(message.chat.id)):
            time_roulette[str(message.chat.id)] = time.time()

        save_roulette(roulette_bids)
    
    @bot.message_handler(commands=['spin'])
    def cmd_spin(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        chat_id = message.chat.id
        args = message.text.lower().split()
        if str(user_id) not in users:
            register(message, bot, types, users)
            return
        
        if time_roulette.get(str(chat_id)):
            if time.time() - time_roulette[str(chat_id)] < KD_ROULETTE:
                bot.reply_to(message, f'⏳ Подождите еще {KD_ROULETTE - int(time.time() - time_roulette[str(chat_id)])} сек.')
                return
            del time_roulette[str(chat_id)]
        
        number = random.choice(ROULETTE_NUMBERS)
        
        if not roulette_bids.get(str(message.chat.id)):
            bot.reply_to(message, '❌ На данный момент нету ни одной ставки в этом чате.')
            return
        elif roulette_bids[str(message.chat.id)] == {}:
            del roulette_bids[str(message.chat.id)]
            bot.reply_to(message, '❌ На данный момент нету ни одной ставки в этом чате.')
            return
        
        winners = []
        for uid, bids in roulette_bids[str(message.chat.id)].items():
            for bid in bids:
                if str(bid[1]) == number['color'] or bid[1] == number['number']:
                    winners.append([uid, users[str(uid)]['name'], bid[0], bid[2], bid[1]])
        
        if number['color'] == 'red':
            text = f'Выпало {number['number']}🔴\n\n'
        elif number['color'] == 'black':
            text = f'Выпало {number['number']}⚫️\n\n'
        elif number['color'] == 'green':
            text = f'Выпало {number['number']}🟢\n\n'
        
        if winners == []:
            text += 'Никто не выиграл...'
        else:
            for winner in winners:
                users[str(winner[0])]['money'] += winner[2] * winner[3]
                log(winner[0], f'Roulette: [WIN] Won bid [{winner[4]}] (+{winner[2] * winner[3]})')
                databack['money'] -= winner[2] * winner[3]
                text += f'<a href="tg://user?id={winner[0]}">{winner[1]}</a> выиграл {winner[2] * winner[3]} {get_coin_form(winner[2] * winner[3])}\n'

        bot.send_message(message.chat.id, text, parse_mode='HTML')
        if roulette_bids.get(str(message.chat.id)):
            del roulette_bids[str(message.chat.id)]
        
        save_roulette(roulette_bids)
        bank_save(databank)
    
    @bot.message_handler(commands=['my_bid'])
    def cmd_delete_bid(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        args = message.text.lower().split()
        if str(user_id) not in users:
            register(message, bot, types, users)
            return

        user = users[str(user_id)]
        
        if not roulette_bids.get(str(message.chat.id), {}).get(str(user_id)):
            bot.reply_to(message, 'У вас нету ставки в данном чате...')
            return        

        mar = types.InlineKeyboardMarkup()
        mar.add(types.InlineKeyboardButton('❌ ОТМЕНИТЬ СТАВКУ', callback_data=f'roulette:{user_id}:cancel:{message.chat.id}'))
        
        text = '💎 Ваши ставки:\n\n'

        for bida in roulette_bids[str(message.chat.id)][str(user_id)]:
            bid = bida[0]
            bet_type = bida[1]
            text += f' - {bid} {get_coin_form(bid)} на {str(bet_type).upper()}\n'
        
        text += '\n\n🎰 Введите /spin чтобы покрутить рулетку.'

        bot.reply_to(message, text, reply_markup=mar)

    @bot.message_handler(commands=['moreless'])
    def cmd_modeless(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        args = message.text.lower().split()
        if str(user_id) not in users:
            register(message, bot, types, users)
            return
        
        user = users[str(user_id)]

        if len(args) != 2:
            bot.reply_to(message, "Введите ставку после команды и угадайте, какое число будет следуйщим\n\n`/moreless <bid>`", parse_mode='markdown')
            return
        
        if args[1] in ['all', 'все', 'вся', 'весь']:
            bid = round(user['money'], 2)
        
        elif not args[1].replace('.', '', 1).isdigit():
            bot.reply_to(message, "Введите ставку после команды и угадайте, какое число будет следуйщим\n\n`/moreless <bid>`", parse_mode='markdown')
            return
        
        bid = round(float(args[1]), 2)
        if bid > round(user['money'], 2):
            bot.reply_to(message, '❌ У вас недостаточно средств')
            return
        
        if bid < 0.1:
            bot.reply_to(message, '❌ Пожалуйста, введите ставку больше 0.1 коина!')
            return
        
        n = random.randint(80, 120)
        
        # bid - 3
        # number - 4

        mar = types.InlineKeyboardMarkup()
        mar.add(types.InlineKeyboardButton('⬆️ БОЛЬШЕ', callback_data=f'moreless:{user_id}:up:{bid}:{n}'))
        mar.add(types.InlineKeyboardButton('⬇️ МЕНЬШЕ', callback_data=f'moreless:{user_id}:down:{bid}:{n}'))
        mar.add(types.InlineKeyboardButton('ОТМЕНИТЬ', callback_data=f'moreless:{user_id}:cancel', style="danger"))

        text = f'Выпало число: <b>{n}</b>'
        bot.reply_to(message, text, reply_markup=mar, parse_mode='HTML')
        bank_save(databank)

    @bot.message_handler(commands=['n', 'number'])
    def cmd_number(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        args = message.text.lower().split()
        if str(user_id) not in users:
            register(message, bot, types, users)
            return
        
        other_data = load_other_data()
        
        if len(args) != 2:
            bot.reply_to(message, f'Угадайте 3-значное число и получите {other_data['number_money']} {get_coin_form(other_data['number_money'])}!\n`/number <number>`', parse_mode='markdown')
            return
        
        if args[1] == 'kd':
            bot.reply_to(message, f'⏳ Cooldown (KD): {round(other_data['number_money'] / 15 + KD_NUMBER, 2)} секунд.')
            return
        
        if not args[1].isdigit():
            bot.reply_to(message, f'Угадайте 3-значное число и получите {other_data['number_money']} {get_coin_form(other_data['number_money'])}!\n`/number <number>`', parse_mode='markdown')
            return
        
        user = users[str(user_id)]

        if not other_time.get('number'):
            other_time['number'] = {}
        if not other_time['number'].get(str(user_id)):
            other_time['number'][str(user_id)] = 0

        if not other_data.get('number'):
            other_data['number'] = random.randint(1, 999)
            other_data['number_money'] = 0
        
        if max(0, time.time() - other_time['number'][str(user_id)]) < other_data['number_money'] / 15 + KD_NUMBER:
            bot.reply_to(message, f'⏳ Повторите через {round(other_data['number_money'] / 15 + KD_NUMBER - (time.time() - other_time['number'][str(user_id)]), 4)} сек.')
            return
        
        other_time['number'][str(user_id)] = time.time()
        
        if int(args[1]) == other_data['number']:
            other_data['number'] = random.randint(1, 999)
            user['money'] += float(other_data['number_money'])
            databank['money'] -= float(other_data['number_money'])
            other_data['number_money'] = 0
            save_other_data(other_data)
            bot.reply_to(message, f'✅ Вы угадали число и получили {float(other_data['number_money'])} {get_coin_form(float(other_data['number_money']))}!')
            return
        bot.reply_to(message, '❌ Вы не угадали!')

        save_other_data(other_data)
        save_users(users)

    @bot.message_handler(commands=['feedback', 'fb'])
    def cmd_feedback(message):
        if bot_stat(message, bot): return
        user_id = message.from_user.id
        add_chat(message.chat.id)
        args = message.text.split(' ', 3)
        if str(user_id) not in users:
            register(message, bot, types, users)
            return
        other_data = load_other_data()

        if not other_data.get('feedback', {}).get('id'):
            other_data['feedback'] = {}
            other_data['feedback']['users'] = []
            other_data['feedback']['id'] = {}
        
        if len(args) > 3:
            args[1] = args[1].lower()
            if not args[1] in ['answer', 'cancel']:
                return
            
            if args[1] == 'answer' and user_id in OWNER:
                try:
                    feedback_id = int(args[2])
                except:
                    return
                
                feedback_user_id = None
                for i, uid in other_data['feedback']['id'].items():
                    if str(feedback_id) == i:
                        feedback_user_id = uid
                        break
                
                if not feedback_user_id:
                    bot.reply_to(message, 'Айди не найден!')
                    return
                
                try:
                    bot.send_message(feedback_user_id, f'✉️ Ответ от разработчика\n\n{args[3]}', parse_mode='HTML', disable_web_page_preview=True)
                    bot.reply_to(message, '✅ Сообщение отправлено!')
                except:
                    bot.reply_to(message, '❌ Произошла неизвестная ошибка. Сообщение не доставлено.')
                    return
                
                del other_data['feedback']['id'][args[2]]
                save_other_data(other_data)
                return
        
        if other_time.get('feedback', {}).get(str(user_id)):
            if time.time() - other_time['feedback'][str(user_id)] < KD_FEEDBACK:
                t = KD_FEEDBACK - (time.time() - other_time['feedback'][str(user_id)])
                bot.reply_to(message, f'⏳ Подождите {int(t // 60)} мин {int(t % 60 // 1)} сек')
                return

        for user in other_data['feedback']['users']:
            if user == user_id:
                other_data['feedback']['users'].remove(user_id)
                break
        
        other_data['feedback']['users'].append(user_id)

        mar = types.InlineKeyboardMarkup()
        mar.add(types.InlineKeyboardButton('❌ ОТМЕНИТЬ', callback_data=f'feedback:{user_id}:cancel'))

        bot.send_message(user_id, '✉️ Отправьте анонимное сообщение разработчику.', reply_markup=mar)
        if message.chat.type != 'private':
            bot.reply_to(message, 'Перейдите в <a href="t.me/gosha2200m_bot">ЛС</a>', parse_mode='HTML', disable_web_page_preview=True)

        save_other_data(other_data)

    @bot.message_handler(commands=['info'])
    def cmd_info(message):
        chat_id = message.chat.id
        chat = message.chat

        text = f"Chat_id: {chat_id}\nChat_type: {chat.type}\n"

        if chat.type == 'private':
            f_name = chat.first_name
            l_name = chat.last_name
            username = chat.username
            bio = chat.bio
            text += f'First name: {f_name}\nLast name: {l_name}\nUsername: {username}\nBio: {bio}'
        
        else:
            desc = chat.description
            link = chat.invite_link
            text = f'Name: {chat.title}\n' + text +  f'Description: {desc}\nLink: {link}'

        bot.reply_to(message, text)

    @bot.message_handler(commands=['answer'])
    def cmd_answer(message):
        answer = message.text.replace('/answer', '', 1).replace('^', '**').replace('pi', '3.14159265').replace('G', '(6.67430*10**(-11))').replace('c', '299792458')

        try:
            result = safe_calc(answer)
        except Exception as e:
            bot.reply_to(message, f'Error! {e}')
            return
        bot.reply_to(message, f"Example: <code>{answer}</code>\n\nAnswer: <code>{result}</code>", parse_mode='HTML')

    @bot.message_handler(commands=['me', 'm'])
    def cmd_rp_me(message):
        user = message.from_user
        rp_text = message.text.split(' ', 1)[1][:512]
        name = users.get(str(user.id), {}).get('name', user.first_name)

        text = f'<a href="tg://user?id={user.id}">{name}</a> {rp_text}'

        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(message.chat.id, text, parse_mode='HTML')

    @bot.message_handler(commands=['log', 'logs'])
    def cmd_logs(message):
        user_id = message.from_user.id
        args = message.text.split()

        us_id = None

        if user_id in OWNER and len(args) == 2:
            id = int(args[1])
            for uid, data in users.items():
                if data['gid'] == id:
                    us_id = uid
        else:
            us_id = user_id

        if us_id == None:
                return

        log = ''
        try:
            with open(f'Logs/{us_id}.txt', 'r') as f:
                lines = f.readlines()[-200:]
                for line in lines:
                    if len(log) > 3000:
                        break
                    log += line
        except:
            log += 'Empty...'
        
        bot.send_message(user_id, f'Ваши последние логи, {users[str(us_id)]['name']}\n\n<blockquote expandable>{log}</blockquote>', parse_mode='HTML')

    @bot.message_handler(commands=['q'])
    def cmd_quote(message):
        path_file = "dp/quotes.json"

        if not os.path.exists(path_file):
            with open(path_file, 'w') as f:
                f.write('{"id": 1}')
        with open(path_file, 'r') as f:
            data = json.load(f)
        
        try:
            text = message.text.split('\n', 1)[1]
        except:
            bot.reply_to(message, "❌ <b>Вы ввели пустую цитату или не перевели строку после команды.</b> После команды перейдите на следующую строку и напишите свою цитату.\n\n💡 <b>Пример использования</b>\n<blockquote>/q\nПишите своб цитату здесь.\nВ цитатах можно переводить строки.</blockquote>", parse_mode="HTML")
            return

        last_id = data['id']
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        date = f"{datetime.now().replace(microsecond=0)}"
        
        quo = data.setdefault(str(last_id), {})
        quo['id'] = user_id
        quo['name'] = user_name
        quo['date'] = f"{date}"
        quo['text'] = text
        quo['like'] = []
        quo['dislike'] = []
        quo['verified'] = None
        data['id'] += 1

        with open(path_file, 'w') as f:
            json.dump(data, f, indent=4)

        bot.reply_to(message, f"✅ <b>Вы добавили цитату №{data['id'] - 1}</b>\n\n📝 Посмотреть все свои цитаты вы можете с помощью команды /my_quotes", parse_mode="HTML")

    @bot.message_handler(commands=['sq', 'search_quote'])
    def cmd_search_quote(msg):
        path_file = "dp/quotes.json"

        with open(path_file, 'r') as f:
            data = json.load(f)
        if len(data) < 2:
            bot.reply_to(msg, "❌ <b>У гоши пока что нет никаких цитат :(</b>\nИспользуйте /q для создания цитат.", parse_mode="HTML")
            return
        
        qid = None
        args = msg.text.split()
        if len(args) == 2 and args[1].isdigit():
            qid = args[1]
            if not data.get(qid, None):
                bot.reply_to(msg, "❌ <b>Такой цитаты не существует!</b>", parse_mode='HTML')
                return

        only_verified = True if len(args) == 2 and args[1] == 'm' else False
        
        no_verif = []
        if only_verified:
            for key, quote in data.items():
                if key == 'id':
                    continue
                if quote['verified'] is False:
                    no_verif.append(key)
            
            bot.reply_to(msg, f"ID of unverified quotes\n\n{', '.join(map(str, no_verif))}")
            return

        qid = qid if qid else str(random.randint(1, data['id'] - 1))

        quote = data[qid]
        if quote['verified'] is False:
            return
        text = quote['text']
        uid = quote['id']
        name = quote['name']
        date = quote['date']

        if not str(uid) in users:
            author = name
        else:
            author = users[str(uid)]['name']

        # Keyboard
        mar = types.InlineKeyboardMarkup()
        mar.add(types.InlineKeyboardButton(f'{len(quote["like"])} 👍', callback_data=f"quote:0:{qid}:like"), types.InlineKeyboardButton(f'{len(quote["dislike"])} 👎', callback_data=f"quote:0:{qid}:dislike"))
        mar.add(types.InlineKeyboardButton('⚠ Report', callback_data=f"quote:0:{qid}:report", style='danger'))

        recent_text = f"💬 Цитата №{qid}\n<blockquote>{text}</blockquote>\n\n👤 <b>Автор:</b> {author}\n⏰ <b>Дата:</b> {date} по UTC"
        bot.reply_to(msg, recent_text, parse_mode="HTML", reply_markup=mar)

    @bot.message_handler(commands=['mq', 'my_quotes'])
    def cmd_my_quotes(message, page=1):
        path_file = "dp/quotes.json"

        with open(path_file, 'r') as f:
            data = json.load(f)

        user = message.from_user

        quotes_id = []
        for qid, quote in data.items():
            if qid.isdigit() and quote['id'] == user.id:
                quotes_id.append(int(qid))

        if len(quotes_id) == 0:
            bot.reply_to(message, "❌ <b>Вы еще не создали никаких цитат :(</b>\nСоздайте свою первую цитату с помощью /q", parse_mode='HTML')
            return

        page_data = other_data.setdefault('mq', {})
        page_data[str(user.id)] = page

        quotes_per_page = QUOTES_PER_PAGE
        total_page = (len(quotes_id) + quotes_per_page - 1) // quotes_per_page
        page_start = (page - 1) * quotes_per_page
        page_end = page_start + quotes_per_page

        mar = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("<", callback_data=f"mq:{user.id}:down:{page}")
        btn2 = types.InlineKeyboardButton(">", callback_data=f"mq:{user.id}:up:{page}")
        mar.add(btn1, btn2)


        quotes = quotes_id[page_start:page_end]

        text = f"💬 <b>Ваши цитаты</b>\nСтраница: {page}/{total_page}"
        for quote_id in quotes:
            quote = data[str(quote_id)]

            quote_text = quote['text']
            quote_date = quote['date']

            text += f"\n\n№{quote_id} ¦ {quote_text[:20]}...\nДата: {quote_date}"

        bot.reply_to(message, text, parse_mode="HTML", reply_markup=mar)

    @bot.message_handler(commands=['mine', 'miner'])
    def cmd_mine(msg):
        if bot_stat(msg, bot): return
        user_id = msg.from_user.id
        add_chat(msg.chat.id)
        if str(user_id) not in users:
            register(msg, bot, types, users)
            return
        user = users[str(user_id)]
        def is_valid_nonce(seed, nonce, target):
            message = seed + str(nonce)
            hash_hex = hashlib.sha256(message.encode('utf-8')).hexdigest()
            return int(hash_hex, 16) < target, hash_hex

        default_time = 60 * 30
        mine_path = 'dp/mine_data.json'
        if not os.path.exists(mine_path):
            with open(mine_path, 'w') as f:
                f.write("{}")
        with open(mine_path, 'r') as f:
            data = json.load(f)

        with open("dp/mine_history.json", 'r') as f:
            mine_history = json.load(f)
        if not mine_history:
            current_time = default_time
        else:
            blocks = list(mine_history.values())
            blocks.sort(key=lambda b: b["time"])
            last_block = blocks[-1]
            last_time = last_block['time']
            current_time = time.time() - last_time
            
        # Var
        size_token = 32
        
        max_target = (2**16 - 1) << 212
        
        data.setdefault('seed', secrets.token_bytes(size_token).hex())
        data.setdefault('target', int(max_target))

        seed = data['seed']
        target = data['target']
        difficult = round(max_target / target)



        reward = 50

        with open(mine_path, 'w') as f:
            json.dump(data, f, indent=4)

        args = msg.text.split()
        if len(args) != 2:
            bot.reply_to(msg, f'🪙 <b>Майнинг</b>\n\n🎯 <b>Цель</b>\nНайти число "nonce", при котором <code>int(sha256(seed + str(nonce)), 16) &lt; target </code>\nSHA-256 считается от UTF-8 строки.\n\n📋 <b>Информация</b>\n• Seed: <code>{seed}</code>\n• Target: <code>{target}</code> (Difficult {difficult})\n• Reward: {reward} coins\n\n💡 Бот проверяет nonce по такой команде Python: <code>int(hashlib.sha256((seed + str(nonce)).encode("utf-8")).hexdigest(), 16) &lt target</code>\n\n📝 Используйте <code>/miner nonce</code> для получения награды.', parse_mode = 'HTML')
            return
        
        try:
            nonce = int(args[1])
        except:
            bot.reply_to(msg, "Это не число.")
            return
        
        is_valid, _hash = is_valid_nonce(seed, nonce, target)
        if is_valid:
            data['seed'] = _hash
            with open(mine_path, 'w') as f:
                json.dump(data, f, indent=4)

            with open("dp/mine_history.json", 'r') as f:
                history = json.load(f)
            
            med_len = 5
            if len(history) % med_len == 0:
                #  Total blocks: med_len + 1
                history_values = sorted(history.values(), key=lambda x: x['time'])[-(med_len + 1):]
                time_list = []
                for i in range(1, med_len + 1):
                    last_time = history_values[i - 1]['time']
                    current_time = history_values[i]['time']
                    total_time = current_time - last_time
                    time_list.append(total_time)

                sort_time = sorted(time_list)
                time_med = sort_time[len(sort_time)//2]

                data['target'] = target = int(max(target / 4, min(max_target, min(target * 4, (target / (default_time / time_med))))))

                with open(mine_path, 'w') as f:
                    json.dump(data, f, indent=4)

            history[seed] = {}
            hd = history[seed]
            hd["seed"] = seed
            hd["difficult"] = difficult
            hd['target'] = target
            hd['nonce'] = nonce
            hd['user_id'] = msg.from_user.id
            hd['date'] = f"{datetime.now()}"
            hd['time'] = time.time()
            
            with open("dp/mine_history.json", 'w') as f:
                json.dump(history, f, indent=2)

            user['money'] += reward
            logger.info(f"Found block, user id: {msg.from_user.id}")
            with open("dp/mine_history.txt", 'a') as f:
                f.write(f"[{hd['date']}] Found nonce.\nSeed: {hd['seed']}\nTarget: {hd['target']}\nNonce: {hd['nonce']}\nUser_id: {hd['user_id']}")

            bot.reply_to(msg, f"Поздравляю! Вы получили <code>{reward}</code> коинов!\nSeed был обновлен\n\n- Hash: <code>{_hash}</code>\n- Seed: <code>{seed}</code>\n- Nonce: <code>{nonce}</code>\n\nUnix Time: <code>{hd['time']}</code>\nTime: {time.ctime(hd['time'])}", parse_mode='HTML')
        else:
            bot.reply_to(msg, f"Nonce неверный!")
        save_users(users)

    @bot.message_handler(commands=['miner_info'])
    def cmd_miner_info(msg): 
        with open("dp/mine_history.json", 'r') as f:
            history = json.load(f)

        blocks_len = len(history)

        text = f"All blocks: {blocks_len}\n\nWrite /miner"

        bot.reply_to(msg, text)

     
    @bot.message_handler(commands=['user_info'])
    def cmd_my_info(msg):
        info = msg.from_user.to_dict()
        if msg.reply_to_message:
            info = msg.reply_to_message.from_user.to_dict()
        
        args = msg.text.split()[1:]

        if not ('-a' in args or '--all' in args):
            info = {k: v for k, v in info.items() if v is not None}
            if not info: info = {"data": "Empty"}
            
        if '-j' in args or '--json' in args:
            info_str = json.dumps(info, indent=2)
            text = f"```json\n{info_str}```"
            bot.reply_to(msg, text, parse_mode="markdown")
            return

        
        text = ""
        i = 1
        for key, value in info.items():
            text += f"{i}. {key}: {value}\n"
            i += 1
        bot.reply_to(msg, text)

    @bot.message_handler(commands=['sha256'])
    def cmd_sha256(msg):
        text = msg.text.split(' ', 1)[1].strip()
        encoding = "utf-8"

        hash_hex = hashlib.sha256(text.encode(encoding)).digest().hex()

        bot.reply_to(msg, f"Текст: <code>{text}</code>\nКодировка: <code>{encoding}</code>\n\nSHA256: <code>{hash_hex}</code>", parse_mode='HTML')

    @bot.message_handler(commands=['sha256hex'])
    def cmd_sha256(msg):
        text = msg.text.split(' ', 1)[1].strip()
        byte_data = bytes.fromhex(text)

        hash_hex = hashlib.sha256(byte_data).digest().hex()

        bot.reply_to(msg, f"Hex: <code>{text}</code>\n\nSHA256: <code>{hash_hex}</code>", parse_mode='HTML')

    @bot.message_handler(commands=['donate'])
    def cmd_donate(msg):
        if bot_stat(msg, bot): return
        user_id = msg.from_user.id
        add_chat(msg.chat.id)
        add_user(user_id, bot)
        databank = bank_load()
        bank_update(user_id, databank, users)
        usernam(user_id, bot)
        args = msg.text.split()

        if len(args) != 2:
            bot.reply_to(msg, "Пожертвуйте несколько коинов в банк!\n\nИспользоваие: <code>/donate сумма</code>", parse_mode='HTML')
            return

        donate_sum = args[1]
        if not donate_sum.replace('.', '', 1).isdigit():
            bot.reply_to(msg, "Пожалуйста, введите сумму коинов для пожертвования.")
            return
        
        user = users.get(str(msg.from_user.id), None)

        if not user:
            bot.reply_to(msg, "хз, ты не зареган")
            return

        donate_sum = round(float(donate_sum), 2)

        if donate_sum > user['money']:
            bot.reply_to(msg, "У вас недостаточно средств! Посмотрите свой баланс с помощью команды /money")
            return

        if donate_sum < 1:
            bot.reply_to(msg, "Сумма должна быть больше или равна 1 коину")
            return

        user['money'] -= donate_sum
        databank['money'] += donate_sum
        
        bank_save(databank)
        save_users(users)

        bot.reply_to(msg, f"Вы успешно пожертвовали {donate_sum} в банк!")

 
    @bot.message_handler(func=lambda message: True, content_types=['text', 'animation', 'photo', 'video', 'document', 'sticker', 'voice', 'audio', 'location', 'contact'])
    def text(message):
        users = load_users()

        user_id = message.from_user.id
        add_chat(message.chat.id)
        top_add(user_id, message.chat.id)
        databank = bank_load()
        username = message.from_user.username
        usernam(user_id, bot)
        other_data = load_other_data()
        if str(user_id) in users:
            gid_add(user_id)
        
        if True:
            chat_id = str(message.chat.id)

            if not os.path.exists('dp/chats.json'):
                with open('dp/chats.json', 'w') as f:
                    f.write('{}')

            with open('dp/chats.json', 'r') as f:
                data = json.load(f)

            if not data.get(chat_id):
                data[chat_id] = {}

            today = datetime.now().strftime("%Y-%m-%d")

            if not data[chat_id].get(today):
                data[chat_id][today] = {}

            chat = data[chat_id][today]

            if not chat.get(str(user_id)):
                chat[str(user_id)] = 1
            else:
                chat[str(user_id)] += 1

            with open('dp/chats.json', 'w') as f:
                json.dump(data, f, indent=2)

        if message and message.content_type == 'text':
            text = message.text.lower()
            args = text.split()

            if text in ['бот', 'гоша', 'долбоеб']:
                if bot_stat(message, bot): return
                bot.reply_to(message, f"<b>{random.choice(MESSAGE_GOSHA)}</b>", parse_mode='HTML')
            
            elif text == 'шип':
                if bot_stat(message, bot): return
                if message.chat.id > 0:
                    bot.reply_to(message, "Это не группа!")
                    return

                us = []
                for user_id in users:  # лучше переименовать id в user_id для ясности
                    if message.chat.id in users[user_id].get('chat', []):
                        # Используем user_id напрямую, так как это уже ID пользователя
                        us.append({
                            'id': user_id,  # используем user_id как ID пользователя
                            'name': users[user_id].get('name', 'Unknow')
                        })

                if len(us) >= 2:
                    user1 = random.choice(us)
                    user2 = random.choice(us)
                    
                    bot.reply_to(message, 
                        f"Рандом шип\n\n"
                        f"<a href=\"tg://user?id={user1['id']}\">{user1['name']}</a> и "
                        f"<a href=\"tg://user?id={user2['id']}\">{user2['name']}</a>", 
                        parse_mode="HTML")
                else:
                    bot.reply_to(message, "Нужно как минимум 2 пользователя в чате!")
            
            elif args[0] in ['.казино', 'казик', 'деп', 'депнуть', 'casino'] and len(args) >= 2 and False:
                return
                if bot_stat(message, bot): return
                user_id = message.from_user.id
                add_chat(message.chat.id)
                if str(user_id) not in users:
                    register(message, bot, types, users)
                    return
                databank = bank_load()
                bank_update(user_id, databank, users)
                usernam(user_id, bot)
                databank = bank_load()

                casino_warning = users[str(user_id)].get('settings', {}).get('notifications', {}).get('casino_warning', True)

                if len(args) < 2:
                    bot.reply_to(message, "❌ Ошибка!\n\nДля подробной информации о казино введите /help_casino\nИспользование:\n/casino 10")
                    return
                
                args[1] = args[1].replace(',', '.', 1)

                money = float(users[str(user_id)].get('money', 0))
                bid = 0

                if args[1].lower() in ['все', 'весь', 'all']:
                    if money < MIN_BET_CASINO:
                        bot.reply_to(message, f"❌ Ошибка!\n\nВводите сумму больше {MIN_BET_CASINO}!")
                        return
                    bid = money
                try:
                    if bid == 0:
                        bid = float(args[1])

                    if bid < MIN_BET_CASINO:
                        bot.reply_to(message, f"❌ Ошибка!\n\nВводите сумму больше {MIN_BET_CASINO}!")
                        return
                    elif bid > MAX_BET_CASINO:
                        bot.reply_to(message, f"Введите сумму меньше {MAX_BET_CASINO}!")
                        return
                except:
                    bot.reply_to(message, "❌ Ошибка!\n\nВводите число. Например: 3.14")
                    return

                if bid > money:
                    bot.reply_to(message, "❌ Ошибка!\n\nНедостаточно средств. Для просмотра баланса введите /money")
                    return
                
                multi_arg = None
                if len(args) > 2:
                    try:
                        multi_arg = round(float(args[2]), 2)
                        if multi_arg <= 1:
                            bot.reply_to(message, "❌ Множитель должен быть больше 1!")
                            return
                    except:
                        bot.reply_to(message, "❌ Ошибка!\n\nВводите число. Например: 3.14")
                        return
                
                if bid >= money / 2:
                    if casino_warning:
                        mar = types.InlineKeyboardMarkup()
                        if multi_arg:
                            mar.add(types.InlineKeyboardButton('ПОДТВЕРДИТЬ', callback_data=f'casino:{user_id}:{bid}:{multi_arg}', style="success"))
                        else:
                            mar.add(types.InlineKeyboardButton('ПОДТВЕРДИТЬ', callback_data=f'casino:{user_id}:{bid}:2', style="success"))
                        mar.add(types.InlineKeyboardButton('ОТМЕНИТЬ', callback_data=f'casino:{user_id}:cancel', style="danger"))
                        bot.reply_to(message, f'<a href="tg://user?id={user_id}">{users[str(user_id)].get('name', 'Unknown')}</a>, ваша ставка превышает 50% вашего баланса! Вы уверены?', parse_mode='HTML', reply_markup=mar)
                        return

                a = random.random()

                if multi_arg:
                    p_chance = round(0.95 / multi_arg, 5)

                    if a <= p_chance:
                        p = 1
                    else:
                        p = 0
                else:
                    if a <= 0.525:
                        p = 0
                    elif a > 0.475:
                        p = 1
                multi_arg = multi_arg or 2
                if bid * multi_arg - bid > databank['money']:
                    bot.reply_to(message, '❌ Недостаточно денег в банке.')
                    return

                if p == 1:
                    if multi_arg:
                        multi = multi_arg
                    else:
                        multi = 2
                    win = round(bid * multi / 100 * (100 - CASINO_COMISSION), 2) # bid * multi - commission
                    users[str(user_id)]['money'] += win
                    databank['money'] -= win

                    log(user_id, f"Casino: [WIN] {bid} coins -> {win} ({multi}x) coins (+{win - bid})")
                    logger.info(f"user {user_id} won in /casino; {bid} -> {win} ({multi}x) conins (+{win - bid})")

                    text = f"✅ <b>Успех!</b>\n\nВы выиграли {win} {get_coin_form(win)}! (+{round(win - bid, 2)}, {multi}x)"


                    result, jackpot, users[str(user_id)] = casino_add(bid * multi - win, win, users[str(user_id)])
                    if result:
                        text = f"🎉 <b>JACKPOT</b>\n\nВы получили {jackpot + win} {get_coin_form(jackpot + win)}! (+{round(jackpot + win - bid)})"

                    if random.random() < 0.01:
                        text += '\n\nВозникли вопросы? Напишите мне через /feedback!'

                    bot.reply_to(message, text, parse_mode='HTML')

                elif p == 0:
                    multi = 0
                    loser = round(bid * multi / 100 * (100 - CASINO_COMISSION), 2) # bid + multi - commission
                    databank['money'] -= loser
                    users[str(user_id)]['money'] += loser

                    log(user_id, f"Casino: [LOSS] {bid} coins -> {loser} ({multi}x) coins (-{bid - loser})")
                    logger.info(f"user {user_id} lost in /casino; {bid} -> {loser} ({multi}x) conins (+{bid - loser})")

                    text = f"❌ <b>Неудача!</b>\n\nВы получили {loser} {get_coin_form(bid)}! ({round(loser - bid, 2)}, {multi}x)"


                    result, jackpot, users[str(user_id)] = casino_add(0, loser, users[str(user_id)])

                    if result:
                        text = f"🎉 <b>JACKPOT</b>\n\nВы получили {jackpot + loser} {get_coin_form(jackpot + loser)}! (+{round(jackpot + loser - bid)})"
                   
                    if random.random() < 0.01:
                        text += '\n\nВозникли вопросы? Напишите мне через /feedback!'

                    bot.reply_to(message, text, parse_mode='HTML')
                
                users[str(user_id)]['money'] -= bid
                save_users(users)
                databank['money'] += bid
                bank_save(databank)

            elif text in ['farm', 'farma', 'фарм', 'заработать', 'поработать', 'работа', 'добыть', 'нафармить']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = message.from_user.id
                add_chat(message.chat.id)
                if str(user_id) not in users:
                    register(message, bot, types, users)
                    return

                user = users[str(user_id)]

                if user['money'] > 1000:
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

                if p < 0.01:
                    if hide_balance:
                        bot.reply_to(message, f'✅ <b>Удача на вашей стороне!</b>\n\nВы нафармили {money:.2f} ({MULTI_FARM}x) {get_coin_form(money)}. Смотрите баланс с помощью команды /money', parse_mode='HTML')
                    else:
                        bot.reply_to(message, f'✅ <b>Удача на вашей стороне!</b>\n\nВы нафармили {money:.2f} ({MULTI_FARM}x) {get_coin_form(money)}.\nВаш баланс: {round(user['money'], 2)} {get_coin_form(round(user['money'], 2))}', parse_mode='HTML')
                else:
                    if hide_balance:
                        bot.reply_to(message, f'✅ <b>Успешно!</b>\n\nВы нафармили {money:.2f} {get_coin_form(money)}. Смотрите баланс с помощью команды /money', parse_mode='HTML')
                    else:
                        bot.reply_to(message, f'✅ <b>Успешно!</b>\n\nВы нафармили {money:.2f} {get_coin_form(money)}.\nВаш баланс: {round(user['money'], 2)} {get_coin_form(round(user['money'], 2))}', parse_mode='HTML')

                save_users(users)

            elif text in ['profile', 'профиль', 'проф', 'акк', 'аккаунт', '.инфа', 'моя инфа', 'мой профиль']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = message.from_user.id
                add_chat(message.chat.id)
                bank_update(user_id, databank, users)

                if str(user_id) not in users:
                    register(message, bot, types, users)
                    return

                adm = 'Нет'

                try:
                    id = message.reply_to_message.from_user.id

                    adm = admin_get(user_id)

                    if not adm:
                        id = user_id
                except:
                    id = user_id

                if not str(id) in users:
                    bot.reply_to(message, "❌ У вас нету аккаунта.")
                    return
                
                user = users[str(id)]

                hide_balance, hide_username = False, False
                if user.get('settings'):
                    hide_balance = user['settings']['confid']['hide_balance']
                    hide_username = user['settings']['confid']['hide_username']

                admin = admin_get(id)

                if admin: adm = 'Админ'
                else: adm = 'Пользователь'

                if user.get('data_register'):
                    t = int(user['data_register'])
                else:
                    t = int(time.time())

                time_reg = format_time_data(t)

                if hide_balance == True:
                    bal = 'hidden'
                else:
                    bal = round(user['money'], 2)

                gid = user.get('gid')
                text = f"📊 Профиль {users[str(id)]['name']}\n\nИмя: <code>{users[str(id)]['name']}</code>\nДата регистрации(dd/mm/yy): <code>{time_reg}</code>\nРанг: {adm}\nАйди: <code>{gid}</code>\n"
                if not hide_balance:
                    text += f"Баланс: <code>{bal}</code> {get_coin_form(bal)}\n"
                if not hide_username:
                    username = user.get("username")
                    if not username:
                        text += f"Юзернейм: <code>не указан</code>\n"
                    text += f"Юзернейм: <code>@{username}</code>\n"

                try:
                    bot.reply_to(message, text, parse_mode='HTML')
                except:
                    bot.reply_to(message, text)

            elif args[0] in ['pay', 'перевести', 'перевод', 'скинуть', 'перекинуть']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = message.from_user.id
                add_chat(message.chat.id)
                add_user(user_id, bot)
                bank_update(user_id, databank, users)
                usernam(user_id, bot)

                args = message.text.split()

                if len(args) < 2:
                    bot.reply_to(message, "❌ Неверные аргументы!\n\nПример:\n/pay @username 1.25 <коментарий по желанию")
                    return
                
                try:
                    username = message.reply_to_message.from_user.username
                    args[1] = args[1].replace(',', '.', 1)
                    pay = round(float(args[1]), 2)
                    a = False
                except:
                    try:
                        args[2] = args[2].replace(',', '.', 1)
                        pay = round(float(args[2]), 2)
                        username = f"{args[1][1:]}"
                        a = True
                    except:
                        bot.reply_to(message, "❌ Неверные аргументы!\n\nПример:\n/pay @username 1.25")
                        return
                    
                try:
                    if a:
                        com = message.text.split(' ', 3)[3]
                    else:
                        com = message.text.split(' ', 2)[2]
                except:
                    pass
                
                reply_id = False
                for uid, user_data in users.items():
                    if user_data.get('username') == username:
                        reply_id = int(uid)
                
                if not reply_id:
                    bot.reply_to(message, "❌ Пользователь не найден!")
                    return
                
                u1 = users[str(user_id)]
                u2 = users[str(reply_id)]

                if user_id == reply_id:
                    bot.reply_to(message, "❌ Невозможно перевести коины самому себе!")
                    return

                if pay > u1['money']:
                    bot.reply_to(message, f"❌ Недостаточно средств!")
                    return
                
                if pay < 0.1:
                    bot.reply_to(message, "❌ Сумма должна быть больше 0.1 коина!")
                    return
                
                markup = types.InlineKeyboardMarkup()
                btn1 = types.InlineKeyboardButton('ПОДТВЕРДИТЬ', callback_data=f'pay_accept:{user_id}:{reply_id}:{pay}:{message.chat.id}', style="success")
                btn2 = types.InlineKeyboardButton('ОТМЕНА', callback_data=f'pay_cancel:{user_id}', style="danger")
                markup.add(btn1)
                markup.add(btn2)
                bot.reply_to(message, "Подтвердите перевод.", reply_markup=markup)

            elif text in ['version', 'версия']:
                bot.reply_to(message, f"Version: {VERSION}")
            
            elif text in ['top', 'топ чата', 'топ чат']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = str(message.from_user.id)
                add_chat(message.chat.id)
                if str(user_id) not in users:
                    register(message, bot, types, users)
                    return
                bank_update(user_id, databank, users)

                if message.chat.id > 0:
                    bot.reply_to(message, "❌ Эта команда работает только в группах!")
                    return

                top = 0
                chat_users = []
                for uid, user_data in users.items():
                    if user_data and message.chat.id in user_data.get('chat', []):
                        hide_balance = user_data.get('settings', {}).get('confid', {}).get('hide_balance', False)
                        hide_top = user_data.get('settings', {}).get('confid', {}).get('hide_top', False)
                        
                        if hide_top:
                            continue
                            
                        display_data = user_data.copy()
                        if hide_balance:
                            display_data['money'] = 0
                            
                        chat_users.append((uid, display_data))
                
                if len(chat_users) < 1:
                    bot.reply_to(message, "💤 В чате пока нет пользователей с коинами.")
                    return
                
                chat_users.sort(key=lambda x: x[1].get('money', 0), reverse=True)

                user_position = 0
                text = '<b>ТОП ЧАТА</b>\n\n'
                
                for i, (uid, user_data) in enumerate(chat_users[:15], 1):
                    money = user_data.get('money', 0)
                    name = user_data.get('name', 'Unknow')
                    
                    if user_id == uid:
                        user_position = i
                    
                    # Эмодзи для мест
                    medals = ["🥇", "🥈", "🥉"]
                    medal = medals[i-1] if i <= 3 else f"{i}."
                    
                    # Выделение текущего пользователя
                    if user_id == uid:
                        name = f"✨{name}✨"
                        top = i
                    
                    username = user_data.get('username')
                    if not username:
                        text += f'{medal} <a href="tg://openmessage?user_id={uid}">{name}</a> | {money:.2f} {get_coin_form(round(money, 2))}\n'
                    else:
                        text += f'{medal} <a href=\"https://t.me/{username}">{name}</a> | {round(money, 2)} {get_coin_form(round(money, 2))}\n'
                
                for i, (uid, user_data) in enumerate(chat_users, 1):
                    if user_id == uid:
                        top = i
                
                text += f"\n📊 <b>Вы на</b> <code>{top}</code> <b>месте.</b>"
                text += f"\n👥 <b>Всего в рейтинге:</b> <code>{len(chat_users)}</code>"
                
                bot.reply_to(message, text, parse_mode="HTML")
                
            elif text in ['global_top', 'глобал топ', 'глобальный топ']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = message.from_user.id
                add_chat(message.chat.id)
                add_user(user_id, bot)
                databank = bank_load()
                bank_update(user_id, databank, users)

                text = 'Глобальный топ\n\n<blockquote expandable>'

                user = users.get(str(user_id), {})
                
                chat_users = []
                
                for uid, user_data in users.items():
                    hide_balance = user_data.get('settings', {}).get('confid', {}).get('hide_balance', False)
                    hide_top = user_data.get('settings', {}).get('confid', {}).get('hide_top', False)
                        
                    if hide_top:
                        continue
                        
                    display_data = user_data.copy()
                    if hide_balance:
                        display_data['money'] = 0
                    
                    chat_users.append((uid, display_data))

                chat_users.sort(key=lambda x: x[1].get('money', 0), reverse=True)
                
                for i, (uid, user_data) in enumerate(chat_users[:30], 1):
                    money = user_data.get('money', 0)
                    name = user_data.get('name', 'Unknown')
                    
                    text = text + f'{i}. {name} | {round(money, 2)} {get_coin_form(round(money, 2))}\n'
                
                top = None
                for i, (uid, user_data) in enumerate(chat_users, 1):
                    if uid == str(user_id):
                        top = i
                        break
                
                if top is None:
                    top = "не определено"
                
                bot.reply_to(message, text + f"</blockquote>\n\nВы на {top} месте из {len(chat_users)}.", parse_mode='HTML')

            elif text in ['удалить аккаунт', 'удалить акк']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = str(message.from_user.id)

                if user_id not in users:
                    register(message, bot, types, users)
                
                markup = types.InlineKeyboardMarkup()
                btn1 = types.InlineKeyboardButton("ПОДТВЕРДИТЬ", callback_data=f"delete_account:{user_id}:t", style="success")
                btn2 = types.InlineKeyboardButton("ОТМЕНИТЬ", callback_data=f"delete_account:{user_id}:f", style="danger")
                markup.add(btn1)
                markup.add(btn2)
                bot.reply_to(message, "<b>Подтвердите удаление аккаунта.</b>\nПосле удаления все данные будут удалены!", parse_mode='HTML', reply_markup=markup)

            elif text in ['.имя', 'мое имя']:
                users = load_users()
                nick = users[str(user_id)].get('name', 'Unknown')

                bot.reply_to(message, f'Твой ник: {nick}')

            elif args[0] in ['.кости', 'дайс']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = message.from_user.id

                args = message.text.lower().split()

                if str(user_id) not in users:
                    register(message, bot, types, users)

                if len(args) != 2:
                    bot.reply_to(message, "❌ Неверные аргументы!\n\nИспользование:\n/dice <bid>")
                    return
                
                r_message = message.reply_to_message
                if r_message == None:
                    bot.reply_to(message, "❌ Ответье на сообщение тому, с кем вы хотите сыграть.")
                    return
                rid = r_message.from_user.id
                
                u1 = users.get(str(user_id))
                u2 = users.get(str(rid))

                try:
                    bid = round(float(args[1]), 2)
                except:
                    if args[1] in ['все', 'весь']:
                        bid = round(u1['money'], 2)
                    else:
                        bot.reply_to(message, "❌ Неверные аргументы!\n\nИспользование:\n/dice <bid>")
                        return

                if user_id == rid:
                    bot.reply_to(message, '❌ Нельзя играть с самим собой!')
                    return

                if not u1 or not u2:
                    bot.reply_to(message, '❌ Игрок не зарегестрирован!')
                    return

                if bid <= 0:
                    bot.reply_to(message, "❌ Введите положительную ставку!")
                    return

                if bid > round(u1['money'], 2):
                    bot.reply_to(message, f'❌ У вас недостаточно средств!')
                    return
                elif bid > round(u2['money'], 2):
                    bot.reply_to(message, '❌ У игрока недостаточно средств')
                    return

                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('ПРИНЯТЬ', callback_data=f'dice:{rid}:{user_id}:{bid}', style="success"))
                mar.add(types.InlineKeyboardButton('ОТКЛОНИТЬ', callback_data=f'dice_cancel:0:{user_id}:{rid}', style="danger"))
                if bid % 1 != 0:
                    bot.send_message(message.chat.id, f'<a href="tg://user?id={rid}">{u2['name']}</a>, <a href="tg://user?id={user_id}">{u1['name']}</a> хочет сыграть с вами в кости на {bid} {get_coin_form(bid)}.', parse_mode='HTML', reply_markup=mar)
                else:
                    bot.send_message(message.chat.id, f'<a href="tg://user?id={rid}">{u2['name']}</a>, <a href="tg://user?id={user_id}">{u1['name']}</a> хочет сыграть с вами в кости на {int(bid)} {get_coin_form(int(bid))}.', parse_mode='HTML', reply_markup=mar)

            elif args[0] in ['рулетка', 'крутить']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = message.from_user.id
                add_chat(message.chat.id)
                args = message.text.lower().split()
                if str(user_id) not in users:
                    register(message, bot, types, users)
                    return

                user = users[str(user_id)]

                if len(args) != 3:
                    bot.reply_to(message, 'Играйте в рулетку! Аргументы:\n\n`/roulette <black/red/green or number> <bid>`', parse_mode='markdown')
                    return
                
                bet_type = args[1]

                if bet_type.isdigit():
                    multi = 36
                    if 0 <= int(bet_type) <= 36:
                        bet_type = int(bet_type)
                    else:
                        bot.reply_to(message, '❌ Пожалуйста, введите число от 0 до 36 или цвет!')
                        return
                else:
                    multi = 2
                    if bet_type in ['black', 'черный', 'черная', 'черное', 'чёрное', 'чёрный', 'чёрная', 'ч', 'b']:
                        bet_type = 'black'
                    elif bet_type in ['red', 'красный', 'красная', 'красное', 'к', 'r']:
                        bet_type = 'red'
                    elif bet_type in ['green', 'зеленый', 'зеленая', 'зеленое', 'зелёный', 'зелёная', 'зелёное', 'з', 'g']:
                        bet_type = 'green'
                        multi = 36
                    else:
                        bot.reply_to(message, '❌ Пожалуйста, введите число от 0 до 36 или цвет!')
                        return
                
                if args[2].lower() in ['all', 'все', 'вся', 'весь']:
                    bid = round(user['money'], 2)
                elif args[2].replace('.', '', 1).isdigit():
                    bid = round(float(args[2]), 2)
                else:
                    bot.reply_to(message, 'Играйте в рулетку! Аргументы:\n\n`/roulette <black/red/green or number> <bid>`', parse_mode='markdown')
                    return
                
                if bid > round(user['money'], 2):
                    bot.reply_to(message, '❌ У вас недостаточно средств!')
                    return
                
                elif bid < 0.1:
                    bot.reply_to(message, '❌ Пожалуйста, введите ставку больше 0.1 коина!')
                    return
                
                else:
                    if not roulette_bids.get(str(message.chat.id)):
                        roulette_bids[str(message.chat.id)] = {}
                    if not roulette_bids[str(message.chat.id)].get(str(user_id)):
                        roulette_bids[str(message.chat.id)][str(user_id)] = []
                    roulette_bids[str(message.chat.id)][str(user_id)].append([bid, bet_type, multi])
                
                user['money'] -= bid

                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('ОТМЕНИТЬ СТАВКУ', callback_data=f'roulette:{user_id}:cancel:{message.chat.id}', style="danger"))
                
                bot.reply_to(message, f'🎯 Вы создали ставку {bid} {get_coin_form(bid)} на {str(bet_type).upper()}\n\n🎰 Введите /spin чтобы покрутить рулетку.', reply_markup=mar)

                if not time_roulette.get(str(message.chat.id)):
                    time_roulette[str(message.chat.id)] = time.time()

                save_roulette(roulette_bids)

            elif args[0] in ['бим']:
                users = load_users()
                if bot_stat(message, bot): return
                user_id = message.from_user.id
                add_chat(message.chat.id)
                args = message.text.lower().split()
                if str(user_id) not in users:
                    register(message, bot, types, users)
                    return
                
                user = users[str(user_id)]

                if len(args) != 2:
                    bot.reply_to(message, "Введите ставку после команды и угадайте, какое число будет следуйщим\n\n`/moreless <bid>`", parse_mode='markdown')
                    return
                
                if args[1] in ['all', 'все', 'вся', 'весь']:
                    bid = round(user['money'], 2)
                
                elif not args[1].replace('.', '', 1).isdigit():
                    bot.reply_to(message, "Введите ставку после команды и угадайте, какое число будет следуйщим\n\n`/moreless <bid>`", parse_mode='markdown')
                    return
                else:
                    bid = round(float(args[1]), 2)
                
                if bid > round(user['money'], 2):
                    bot.reply_to(message, '❌ У вас недостаточно средств')
                    return
                
                if bid < 0.1:
                    bot.reply_to(message, '❌ Пожалуйста, введите ставку больше 0.1 коина!')
                    return
                
                n = random.randint(80, 120)
                
                # bid - 3
                # number - 4

                mar = types.InlineKeyboardMarkup()
                mar.add(types.InlineKeyboardButton('⬆️ БОЛЬШЕ', callback_data=f'moreless:{user_id}:up:{bid}:{n}'))
                mar.add(types.InlineKeyboardButton('⬇️ МЕНЬШЕ', callback_data=f'moreless:{user_id}:down:{bid}:{n}'))
                mar.add(types.InlineKeyboardButton('ОТМЕНИТЬ', callback_data=f'moreless:{user_id}:cancel', style="danger"))

                text = f'💎 Ваша ставка: {bid} {get_coin_form(bid)}\n\nВыпало число: <b>{n}</b>'
                bot.reply_to(message, text, reply_markup=mar, parse_mode='HTML')

        # Feedback
        if user_id in other_data.get('feedback', {}).get('users', []):
            if not other_data['feedback'].get('id'):
                other_data['feedback']['id'] = {}

            if message.chat.type == 'private':
                other_data['feedback']['users'].remove(user_id)
                ids = other_data['feedback']['id']
                max_ids = 0
                for i, uid in ids.items():
                    print(f'{i} | {uid}')
                    try:
                        max_ids = max(max_ids, int(i))
                    except:
                        pass
                
                other_data['feedback']['id'][str(max_ids + 1)] = user_id
                try:
                    for uid in OWNER:
                        bot.send_message(uid, f'Пришло анонимное сообщение от пользователя:\n\n<code>{html.escape(message.text)}</code>\n\nДата: <code>{format_time_data_t(time.time())}</code>\nВерсия: <code>{VERSION}</code>\nID: <code>{max_ids + 1}</code>', parse_mode='HTML')
                except:
                    bot.reply_to(message, '❌ Произошла неизвестная ошибка. Сообщение не доставлено.')
                    return
                bot.reply_to(message, '✅ Сообщение отправлено!')

                if not other_time.get('feedback'):
                    other_time['feedback'] = {}
                if not user_id in OWNER:
                    other_time['feedback'][str(user_id)] = time.time()

                save_other_data(other_data)

        if message.forward_from:
            name = message.forward_from.first_name
            bot.reply_to(message, name)
        
        save_other_data(other_data)

        
    return bot

