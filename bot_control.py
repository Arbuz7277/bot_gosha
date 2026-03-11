import telebot
from telebot import types
import time

bot = telebot.TeleBot('8211283729:AAGStw5nfibYhG5XulnU1iG9unRMy6kqqMg')
ADMIN_ID = 8400317551

def load():
    with open('bot_stat.txt', 'r') as f:
        return f.read()

def save(data):
    with open('bot_stat.txt', 'w') as f:
        f.write(data)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    mar = types.InlineKeyboardMarkup()
    mar.add(types.InlineKeyboardButton('❌ ВЫКЛЮЧИТЬ', callback_data='off'))
    mar.add(types.InlineKeyboardButton('✅ ВКЛЮЧИТЬ', callback_data='on'))
    if call.data == 'on':
        save('on')
        data = load()
        try:
            bot.edit_message_text(f"Состоние: {data}", call.message.chat.id, call.message.message_id, reply_markup=mar)
        except:
            pass
    elif call.data == 'off':
        save('off')
        data = load()
        try:
            bot.edit_message_text(f"Состоние: {data}", call.message.chat.id, call.message.message_id, reply_markup=mar)
        except:
            pass
    bot.answer_callback_query(call.id, 'Изменено!')

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    mar = types.InlineKeyboardMarkup()
    mar.add(types.InlineKeyboardButton('❌ ВЫКЛЮЧИТЬ', callback_data='off'))
    mar.add(types.InlineKeyboardButton('✅ ВКЛЮЧИТЬ', callback_data='on'))
    
    data = load()
    text = f"Состоние: {data}"
    bot.send_message(ADMIN_ID, text, reply_markup=mar)


while True:
    try:
        bot.polling()
    except:
        print("Error!")
        time.sleep(15)